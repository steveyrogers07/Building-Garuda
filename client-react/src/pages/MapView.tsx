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
    { id: "bg", type: "background", paint: { "background-color": "#0b0d11" } },
    { id: "carto", type: "raster", source: "carto", paint: { "raster-opacity": 0.9 } },
  ],
}

function colorFor(t: number): string {
  return t > 0.66 ? "#e5484d" : t > 0.33 ? "#c9a227" : "#8fa3bf"
}

/** Time-of-day bands (the brief's 'spatiotemporal clusters'): layered onto
 *  location server-side via /geo/*?hour_from&hour_to. Night wraps midnight. */
const BANDS = [
  { id: "all", label: "All hours" },
  { id: "morning", label: "Morning", from: 5, to: 12 },
  { id: "afternoon", label: "Afternoon", from: 12, to: 17 },
  { id: "evening", label: "Evening", from: 17, to: 21 },
  { id: "night", label: "Night", from: 20, to: 5 },
] as const

export default function MapView() {
  const navigate = useNavigate()
  const p = usePrincipal()
  const [bandId, setBandId] = useState<(typeof BANDS)[number]["id"]>("all")
  const band = BANDS.find((b) => b.id === bandId)
  const bandParam = band && "from" in band ? { from: band.from, to: band.to } : undefined
  const geo = useApi(() => api.geoDistricts(bandParam), [p?.role, p?.scope, bandId])
  const risk = useApi(() => api.riskTop(20), [p?.role, p?.scope])
  const anomalies = useApi(() => api.anomalies(), [p?.role, p?.scope])
  const [drill, setDrill] = useState<GeoDistrict | null>(null)
  const stations = useApi(
    () => (drill ? api.geoStations(drill.code, bandParam) : Promise.resolve(null)),
    [drill?.code, bandId],
  )

  const mapRef = useRef<MLMap | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])
  const stationMarkersRef = useRef<maplibregl.Marker[]>([])
  const pulseRef = useRef<number | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const districts = geo.data?.districts ?? []
  // districts with an active emerging-trend alert pulse red on the map
  const alertDistricts = new Set(
    (anomalies.data?.sample ?? []).map((a) => a.district_code).filter(Boolean),
  )

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
          alert: alertDistricts.has(d.code) ? 1 : 0,
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
        // red-zone pulsing where a crime category is spiking vs its baseline
        map!.addLayer({
          id: "district-alert-pulse",
          type: "circle",
          source: "districts",
          filter: ["==", ["get", "alert"], 1],
          paint: {
            "circle-radius": ["*", ["get", "r"], 1.4],
            "circle-color": "#e5484d",
            "circle-opacity": 0.18,
            "circle-stroke-width": 2,
            "circle-stroke-color": "#e5484d",
            "circle-stroke-opacity": 0.7,
          },
        })
        if (pulseRef.current == null) {
          const t0 = performance.now()
          const tick = () => {
            const m = mapRef.current
            if (!m || !m.getLayer("district-alert-pulse")) return
            const phase = (Math.sin((performance.now() - t0) / 420) + 1) / 2
            m.setPaintProperty("district-alert-pulse", "circle-radius",
              ["*", ["get", "r"], 1.15 + 0.55 * phase])
            m.setPaintProperty("district-alert-pulse", "circle-stroke-opacity",
              0.25 + 0.55 * (1 - phase))
            pulseRef.current = requestAnimationFrame(tick)
          }
          pulseRef.current = requestAnimationFrame(tick)
        }
        map!.on("click", "district-bubbles", (e) => {
          const code = e.features?.[0]?.properties?.code as string | undefined
          const d = districts.find((x) => x.code === code)
          if (d) {
            setDrill(d)
            map!.flyTo({ center: [d.lng, d.lat], zoom: 8.6, duration: 900 })
          }
        })
        map!.on("mouseenter", "district-bubbles", () => (map!.getCanvas().style.cursor = "pointer"))
        map!.on("mouseleave", "district-bubbles", () => (map!.getCanvas().style.cursor = ""))
      } else {
        ;(map!.getSource("districts") as maplibregl.GeoJSONSource).setData(fc)
      }

      // code labels as HTML markers (own bundled font — no external glyph server)
      markersRef.current.forEach((m) => m.remove())
      markersRef.current = districts.map((d) => {
        const el = document.createElement("span")
        el.textContent = d.code
        el.style.cssText =
          "font:600 10.5px 'IBM Plex Mono',monospace;color:#e9e7e0;letter-spacing:.5px;" +
          "text-shadow:0 0 4px #0b0d11,0 0 3px #0b0d11,0 1px 2px #0b0d11;pointer-events:none"
        return new maplibregl.Marker({ element: el }).setLngLat([d.lng, d.lat]).addTo(map!)
      })
    }

    if (map.isStyleLoaded()) draw()
    else map.once("load", draw)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districts, anomalies.data])

  // stop the pulse animation with the component
  useEffect(() => () => {
    if (pulseRef.current != null) cancelAnimationFrame(pulseRef.current)
  }, [])

  // station markers for the drilled district (Units master names + centroids)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    stationMarkersRef.current.forEach((m) => m.remove())
    stationMarkersRef.current = []
    const rows = drill ? stations.data?.stations ?? [] : []
    if (!rows.length) return
    const maxS = Math.max(1, ...rows.map((s) => s.incidents))
    stationMarkersRef.current = rows
      .filter((s) => s.lat != null && s.lng != null)
      .map((s) => {
        const el = document.createElement("div")
        const r = 7 + 13 * Math.sqrt(s.incidents / maxS)
        el.title = `${s.name} — ${s.incidents} incidents`
        el.style.cssText =
          `width:${r * 2}px;height:${r * 2}px;border-radius:50%;cursor:pointer;` +
          "background:rgba(120,200,255,.25);border:1.5px solid #7cc8ff;" +
          "box-shadow:0 0 8px rgba(124,200,255,.35)"
        return new maplibregl.Marker({ element: el })
          .setLngLat([s.lng as number, s.lat as number])
          .addTo(map)
      })
    return () => {
      stationMarkersRef.current.forEach((m) => m.remove())
      stationMarkersRef.current = []
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drill?.code, stations.data])

  const drillRisk = (risk.data?.top ?? []).filter((r) => r.district_code === drill?.code).slice(0, 3)

  return (
    <>
      <PageHeader
        eyebrow="Investigate · Geography"
        title="Hotspot Map"
        caption="District incident load — bubble size = volume, colour = intensity, halo = top hotspots, red pulse = active spike alert. Click a district to drill to its stations."
      >
        <div
          className="flex flex-wrap items-center gap-0.5 rounded-sm border border-line bg-panel p-0.5"
          role="group"
          aria-label="Time-of-day band"
        >
          {BANDS.map((b) => (
            <button
              key={b.id}
              onClick={() => setBandId(b.id)}
              aria-pressed={bandId === b.id}
              className={
                "rounded-[3px] px-2 py-1 font-mono text-[10.5px] transition-colors " +
                (bandId === b.id ? "bg-brass-soft text-brass" : "text-muted-foreground")
              }
            >
              {b.label}
            </button>
          ))}
        </div>
      </PageHeader>

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div className="relative h-[calc(100vh-262px)] min-h-[440px] overflow-hidden rounded-md border border-line shadow-panel">
          <div ref={containerRef} className="h-full w-full" />
          {/* legend */}
          <div className="absolute bottom-3 left-3 z-10 rounded-sm border border-line bg-console/90 px-3 py-2 font-mono text-[10.5px] text-muted-foreground backdrop-blur">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-steel" /> low
              <span className="size-2 rounded-full bg-brass" /> medium
              <span className="size-2 rounded-full bg-signal" /> high intensity
            </div>
            <div className="mt-1 text-faint">size = incident volume · halo = top-6 hotspot</div>
          </div>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <div className="k-label">Drill-down</div>
            <CardTitle className="t-display mt-1 text-[17px]">District</CardTitle>
          </CardHeader>
          <CardContent>
            {!drill ? (
              <EmptyState>Select a district bubble on the map.</EmptyState>
            ) : (
              <>
                <div className="flex items-start justify-between gap-2">
                  <div className="t-display text-[18px]">{drill.name || drill.code}</div>
                  <button
                    onClick={() => setDrill(null)}
                    className="rounded-sm border border-line bg-panel px-2 py-0.5 font-mono text-[10px] text-muted-foreground hover:text-foreground"
                  >
                    ← state view
                  </button>
                </div>
                {alertDistricts.has(drill.code) && (
                  <div className="mt-2 rounded-sm border border-signal/35 bg-signal/10 px-2 py-1 font-mono text-[10.5px] text-signal">
                    ⚠ active spike alert in this district
                  </div>
                )}
                <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12px]">
                  <span className="k-label">code</span>
                  <span className="font-mono">{drill.code}</span>
                  <span className="k-label">incidents</span>
                  <span className="tnum font-mono">{fmt(drill.incidents)}</span>
                  <span className="k-label">top crime</span>
                  <span>{drill.top_crime || "–"}</span>
                </div>

                <div className="k-label mt-4 mb-1.5">
                  Stations ({band && "from" in band ? band.label.toLowerCase() : "all hours"})
                </div>
                {stations.loading ? (
                  <div className="text-[11.5px] text-faint">Loading stations…</div>
                ) : (
                  <div className="max-h-44 space-y-1 overflow-y-auto pr-1">
                    {(stations.data?.stations ?? []).slice(0, 8).map((s) => (
                      <div
                        key={s.station_code}
                        className="flex items-center justify-between rounded-sm border border-line-soft bg-panel-2/50 px-2 py-1 text-[11px]"
                      >
                        <span className="min-w-0 truncate">{s.name || s.station_code}</span>
                        <span className="tnum ml-2 shrink-0 font-mono text-steel">{s.incidents}</span>
                      </div>
                    ))}
                  </div>
                )}

                {drillRisk.length > 0 && (
                  <>
                    <div className="k-label mt-4 mb-1.5">Forecast risk (next period)</div>
                    <div className="space-y-1.5">
                      {drillRisk.map((r, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-sm border border-line-soft bg-panel-2/50 px-2 py-1.5 text-[11.5px]"
                        >
                          <span>{r.crime_type}</span>
                          <span className="tnum font-mono text-brass">{pct(r.risk_score)}</span>
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
