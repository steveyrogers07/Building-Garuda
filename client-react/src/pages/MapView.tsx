import type { FeatureCollection } from "geojson"
import maplibregl, { Map as MLMap } from "maplibre-gl"
import "maplibre-gl/dist/maplibre-gl.css"
import { MessageSquareText } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import { EmptyState, PageHeader } from "@/components/common/bits"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { fmt, pct } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { usePrincipal } from "@/lib/roles"
import type { GeoDistrict } from "@/lib/types"

/** Free dark basemap (Carto raster, no API key). If tiles can't load (offline
 *  demo), the bubbles still render over the plain dark canvas. */
const DARK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors · © CARTO",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0a1020" } },
    { id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 0.9 } },
  ],
}

function colorFor(t: number): string {
  return t > 0.66 ? "#ef4444" : t > 0.33 ? "#f9a825" : "#3b82f6"
}

export default function MapView() {
  const navigate = useNavigate()
  const p = usePrincipal()
  const geo = useApi(() => api.geoDistricts(), [p?.role, p?.scope])
  const risk = useApi(() => api.riskTop(20), [p?.role, p?.scope])
  const [drill, setDrill] = useState<GeoDistrict | null>(null)

  const mapRef = useRef<MLMap | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const containerRef = useRef<HTMLDivElement>(null)
  const districts = geo.data?.districts ?? []

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: DARK_STYLE,
      bounds: [
        [73.8, 11.4],
        [78.8, 18.6],
      ],
      fitBoundsOptions: { padding: 30 },
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left")
    map.on("error", () => {
      /* tile fetch failures (offline) are non-fatal — bubbles still render */
    })
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // (re)draw district bubbles whenever data arrives
  useEffect(() => {
    const map = mapRef.current
    if (!map || !districts.length) return

    const maxN = Math.max(1, ...districts.map((d) => d.incidents))
    const top = new Set(
      [...districts].sort((a, b) => b.incidents - a.incidents).slice(0, 6).map((d) => d.code),
    )
    const fc: FeatureCollection = {
      type: "FeatureCollection",
      features: districts.map((d) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [d.lng, d.lat] },
        properties: {
          code: d.code,
          r: 8 + 26 * Math.sqrt(d.incidents / maxN),
          c: colorFor(d.incidents / maxN),
          hot: top.has(d.code) ? 1 : 0,
        },
      })),
    }

    function draw() {
      if (!map!.getSource("districts")) {
        map!.addSource("districts", { type: "geojson", data: fc })
        map!.addLayer({
          id: "district-halo",
          type: "circle",
          source: "districts",
          filter: ["==", ["get", "hot"], 1],
          paint: {
            "circle-radius": ["*", ["get", "r"], 1.7],
            "circle-color": ["get", "c"],
            "circle-opacity": 0.12,
            "circle-stroke-width": 1,
            "circle-stroke-color": ["get", "c"],
            "circle-stroke-opacity": 0.35,
          },
        })
        map!.addLayer({
          id: "district-bubbles",
          type: "circle",
          source: "districts",
          paint: {
            "circle-radius": ["get", "r"],
            "circle-color": ["get", "c"],
            "circle-opacity": 0.26,
            "circle-stroke-width": 1.6,
            "circle-stroke-color": ["get", "c"],
          },
        })
        map!.on("click", "district-bubbles", (e) => {
          const code = e.features?.[0]?.properties?.code as string | undefined
          const d = districts.find((x) => x.code === code)
          if (d) setDrill(d)
        })
        map!.on("mouseenter", "district-bubbles", () => (map!.getCanvas().style.cursor = "pointer"))
        map!.on("mouseleave", "district-bubbles", () => (map!.getCanvas().style.cursor = ""))
      } else {
        ;(map!.getSource("districts") as maplibregl.GeoJSONSource).setData(fc)
      }

      // code labels as HTML markers (own Fira font — no external glyph server)
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = districts.map((d) => {
        const el = document.createElement("span")
        el.textContent = d.code
        el.style.cssText =
          "font:600 10.5px 'Fira Code',monospace;color:#e8eef9;letter-spacing:.5px;" +
          "text-shadow:0 0 4px #080d18,0 0 3px #080d18,0 1px 2px #080d18;pointer-events:none"
        return new maplibregl.Marker({ element: el }).setLngLat([d.lng, d.lat]).addTo(map!)
      })
    }

    if (map.isStyleLoaded()) draw()
    else map.once("load", draw)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districts])

  const drillRisk = (risk.data?.top ?? []).filter((r) => r.district_code === drill?.code).slice(0, 3)

  return (
    <>
      <PageHeader
        title="Hotspot Map"
        caption="District incident load — bubble size = volume, colour = intensity, halo = top hotspots. Click a district to drill down."
      />

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="relative h-[calc(100vh-262px)] min-h-[440px] overflow-hidden rounded-lg border shadow-panel">
          <div ref={containerRef} className="h-full w-full" />
          {/* legend */}
          <div className="absolute bottom-3 left-3 z-10 rounded-md border bg-background/85 px-3 py-2 font-mono text-[10.5px] text-muted-foreground backdrop-blur">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-chart-1" /> low
              <span className="size-2 rounded-full bg-amber" /> medium
              <span className="size-2 rounded-full bg-danger" /> high intensity
            </div>
            <div className="mt-1 text-faint">size = incident volume · halo = top-6 hotspot</div>
          </div>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <div className="k-label">Drill-down</div>
            <CardTitle className="mt-1 text-[15px]">District</CardTitle>
          </CardHeader>
          <CardContent>
            {!drill ? (
              <EmptyState>Select a district bubble on the map.</EmptyState>
            ) : (
              <>
                <div className="font-mono text-[15px] font-semibold">{drill.name || drill.code}</div>
                <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
                  <span className="k-label">code</span>
                  <span className="font-mono">{drill.code}</span>
                  <span className="k-label">incidents</span>
                  <span className="tnum font-mono">{fmt(drill.incidents)}</span>
                  <span className="k-label">top crime</span>
                  <span>{drill.top_crime || "–"}</span>
                </div>

                {drillRisk.length > 0 && (
                  <>
                    <div className="k-label mt-4 mb-1.5">Forecast risk (next period)</div>
                    <div className="space-y-1.5">
                      {drillRisk.map((r, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded border border-border-soft bg-surface-2/50 px-2 py-1.5 text-[11.5px]"
                        >
                          <span>{r.crime_type}</span>
                          <span className="tnum font-mono text-amber">{pct(r.risk_score)}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}

                <Button
                  size="sm"
                  variant="outline"
                  className="mt-4 w-full text-[11.5px]"
                  onClick={() => navigate("/copilot", { state: { ask: `crime in ${drill.code}` } })}
                >
                  <MessageSquareText className="size-3.5" /> Ask copilot about {drill.code}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
