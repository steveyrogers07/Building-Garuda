import { MessageSquareText, User } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { PageHeader, ShimmerRows } from "@/components/common/bits"
import { ForceGraph } from "@/components/graph/ForceGraph"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { useApi } from "@/lib/hooks"
import { usePrincipal } from "@/lib/roles"
import type { EgoGraph, GraphNode } from "@/lib/types"
import { cn } from "@/lib/utils"

export default function Network() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const p = usePrincipal()
  const deps = [p?.role, p?.scope]

  const rings = useApi(() => api.rings(6), deps)
  const [focusId, setFocusId] = useState<string | null>(params.get("focus"))
  const [ego, setEgo] = useState<EgoGraph | null>(null)
  const [egoLoading, setEgoLoading] = useState(false)
  const [selected, setSelected] = useState<GraphNode | null>(null)

  const ringRows = rings.data?.rings ?? []
  const activeId = focusId ?? ringRows[0]?.kingpin_id ?? null

  useEffect(() => {
    if (!activeId) return
    let alive = true
    setEgoLoading(true)
    setSelected(null)
    api.ego(activeId, 2).then((g) => {
      if (!alive) return
      setEgo(g)
      setEgoLoading(false)
      const center = (g.nodes || []).find((n) => n.id === activeId)
      if (center) setSelected(center)
    })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, p?.role, p?.scope])

  return (
    <>
      <PageHeader
        title="Co-offender Network Reveal"
        caption={
          <>
            Siloed FIRs → one visible gang. Node size = involvement, colour = community,{" "}
            <span className="text-amber">amber ring = kingpin</span>. First live load computes
            centrality (~1 min).
          </>
        }
      >
        <div className="flex max-w-[520px] flex-wrap justify-end gap-1.5">
          {ringRows.map((r) => (
            <button
              key={r.kingpin_id}
              onClick={() => setFocusId(r.kingpin_id)}
              className={cn(
                "rounded-full border bg-surface-2/60 px-2.5 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground",
                activeId === r.kingpin_id && "border-amber/50 bg-amber-soft text-amber",
              )}
            >
              {r.kingpin_label.split(" ")[0]} · {r.district_count}d
            </button>
          ))}
        </div>
      </PageHeader>

      <div className="relative h-[calc(100vh-262px)] min-h-[460px] overflow-hidden rounded-lg border bg-card shadow-panel">
        {egoLoading || rings.loading ? (
          <div className="p-5">
            <ShimmerRows n={4} h={80} />
          </div>
        ) : ego ? (
          <ForceGraph data={ego} kingpin={activeId ?? undefined} onSelect={setSelected} />
        ) : (
          <div className="flex h-full items-center justify-center text-[12.5px] text-faint">
            No ring selected.
          </div>
        )}

        {/* legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-3 rounded-md border bg-background/85 px-3 py-1.5 font-mono text-[10.5px] text-muted-foreground backdrop-blur">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-chart-1 shadow-[0_0_8px_#3b82f6]" /> community A
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full bg-chart-2 shadow-[0_0_8px_#f9a825]" /> community B
          </span>
          <span className="text-amber">◎ kingpin</span>
          <span>☎ phone · ⌗ vehicle</span>
        </div>

        {/* node detail panel */}
        {selected && (
          <div className="absolute right-3 top-3 w-[248px] rounded-lg border bg-background/92 p-3.5 shadow-pop backdrop-blur">
            <div className="font-mono text-[14px] font-semibold">{selected.label || selected.id}</div>
            <div className="mt-0.5 font-mono text-[10.5px] text-faint">
              {selected.type} · {selected.id}
            </div>
            <div className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[11.5px]">
              <span className="k-label">incidents</span>
              <span className="tnum font-mono">{selected.incident_count ?? 0}</span>
              <span className="k-label">strength</span>
              <span className="tnum font-mono">{selected.strength ?? 0}</span>
              <span className="k-label">betweenness</span>
              <span className="tnum font-mono">{selected.betweenness ?? "–"}</span>
              <span className="k-label">community</span>
              <span className="font-mono">#{selected.community ?? "–"}</span>
              <span className="k-label">districts</span>
              <span className="font-mono">{(selected.districts || []).join(" ") || "–"}</span>
            </div>
            <div className="mt-3.5 space-y-1.5">
              <Button
                size="sm"
                variant="outline"
                className="w-full text-[11.5px]"
                onClick={() => navigate(`/entity/${encodeURIComponent(selected.id)}`)}
              >
                <User className="size-3.5" /> Open dossier
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="w-full text-[11.5px]"
                onClick={() =>
                  navigate("/copilot", { state: { ask: `incidents involving ${selected.label}` } })
                }
              >
                <MessageSquareText className="size-3.5" /> Ask copilot
              </Button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
