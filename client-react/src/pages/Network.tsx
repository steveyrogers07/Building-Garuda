import { MessageSquareText, RotateCcw, User } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { PageHeader, ShimmerRows } from "@/components/common/bits"
import { COMMUNITY, ForceGraph } from "@/components/graph/ForceGraph"
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
  const [run, setRun] = useState(0) // remounts the graph → replays the reveal

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

  /* legend reflects the communities actually present in this ego graph */
  const communities = useMemo(() => {
    const seen = new Set<number>()
    for (const n of ego?.nodes ?? []) if (n.community != null) seen.add(n.community)
    return [...seen].sort((a, b) => a - b).slice(0, 5)
  }, [ego])

  return (
    <>
      <PageHeader
        eyebrow="Investigate · Co-offender graph"
        title="Network Reveal"
        caption={
          <>
            Siloed FIRs → one visible gang. Node size = involvement, colour = community,{" "}
            <span className="text-brass">brass double-ring = kingpin</span>. First live load computes
            centrality (~1 min).
          </>
        }
      >
        <div className="flex max-w-[520px] flex-wrap justify-end gap-1.5">
          {ringRows.map((r, i) => (
            <button
              key={r.kingpin_id}
              onClick={() => setFocusId(r.kingpin_id)}
              className={cn(
                "rounded-sm border border-line bg-panel px-2.5 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-brass/40 hover:text-foreground",
                activeId === r.kingpin_id && "border-brass/50 bg-brass-soft text-brass",
              )}
            >
              <span className="mr-1.5 opacity-60">{String(i + 1).padStart(2, "0")}</span>
              {r.kingpin_label.split(" ")[0]} · {r.district_count}d
            </button>
          ))}
        </div>
      </PageHeader>

      <div className="grid-field relative h-[calc(100vh-262px)] min-h-[460px] overflow-hidden rounded-md border border-line bg-console-deep shadow-panel">
        {egoLoading || rings.loading ? (
          <div className="p-5">
            <ShimmerRows n={4} h={80} />
          </div>
        ) : ego ? (
          <ForceGraph key={run} data={ego} kingpin={activeId ?? undefined} onSelect={setSelected} />
        ) : (
          <div className="flex h-full items-center justify-center text-[12.5px] text-faint">
            No ring selected.
          </div>
        )}

        {/* replay the siloed-FIRs → one-gang entrance */}
        {ego && !egoLoading && (
          <button
            onClick={() => setRun((r) => r + 1)}
            className="absolute right-3 bottom-3 flex items-center gap-1.5 rounded-sm border border-line bg-console/90 px-2.5 py-1.5 font-mono text-[10.5px] text-muted-foreground backdrop-blur transition-colors hover:border-brass/40 hover:text-brass"
          >
            <RotateCcw className="size-3" /> Replay reveal
          </button>
        )}

        {/* legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-3 rounded-sm border border-line bg-console/90 px-3 py-1.5 font-mono text-[10.5px] text-muted-foreground backdrop-blur">
          {communities.map((c) => (
            <span key={c} className="flex items-center gap-1.5">
              <span
                className="size-2 rounded-full"
                style={{ background: COMMUNITY[c % COMMUNITY.length] }}
              />
              community {c}
            </span>
          ))}
          <span className="text-brass">◎ kingpin</span>
          <span>☎ phone · ⌗ vehicle</span>
        </div>

        {/* node detail panel */}
        {selected && (
          <div className="absolute right-3 top-3 w-[248px] rounded-md border border-line bg-console/92 p-3.5 shadow-pop backdrop-blur">
            <div className="t-display text-[17px] leading-tight">{selected.label || selected.id}</div>
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
