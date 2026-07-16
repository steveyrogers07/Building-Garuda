import { Crosshair, MessageSquareText, RotateCcw, Search, User } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { PageHeader, ShimmerRows } from "@/components/common/bits"
import { COMMUNITY, ForceGraph } from "@/components/graph/ForceGraph"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { useApi } from "@/lib/hooks"
import { usePrincipal } from "@/lib/roles"
import type { EgoGraph, GraphNode, SearchEntityHit } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Search-anyone entry point: any name / phone / plate in the corpus resolves
 *  to its canonical entity and recenters the graph — the rings are just
 *  starting points, not the only doors in. */
function EntitySearch({ onPick }: { onPick: (hit: SearchEntityHit) => void }) {
  const [q, setQ] = useState("")
  const [hits, setHits] = useState<SearchEntityHit[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    const query = q.trim()
    if (query.length < 2) {
      setHits([])
      setOpen(false)
      return
    }
    const mine = ++seq.current
    setBusy(true)
    const t = setTimeout(async () => {
      try {
        const res = await api.search(query)
        if (seq.current !== mine) return
        const g = res.groups || {}
        const merged = [...(g.people || []), ...(g.vehicles || []), ...(g.phones || [])]
        merged.sort((a, b) => (b.incidents ?? 0) - (a.incidents ?? 0))
        setHits(merged.slice(0, 8))
        setOpen(true)
      } finally {
        if (seq.current === mine) setBusy(false)
      }
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  return (
    <div className="relative w-full max-w-[340px]">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-faint" />
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => hits.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        placeholder="Trace anyone — name, phone, plate…"
        className="h-8 bg-panel pl-8 font-mono text-[12px]"
        aria-label="Search an entity to trace"
      />
      {open && (
        <div className="absolute z-40 mt-1 w-full overflow-hidden rounded-sm border border-line bg-console/95 shadow-pop backdrop-blur">
          {hits.length === 0 ? (
            <div className="px-3 py-2 text-[11.5px] text-faint">
              {busy ? "Searching…" : "No entity matches in the corpus."}
            </div>
          ) : (
            hits.map((h) => (
              <button
                key={h.canonical_id}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onPick(h)
                  setOpen(false)
                  setQ("")
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12px] text-muted-foreground transition-colors hover:bg-panel hover:text-foreground"
              >
                <span className="w-12 shrink-0 font-mono text-[9.5px] uppercase text-faint">{h.type}</span>
                <span className="min-w-0 flex-1 truncate font-mono">{h.masked || h.value}</span>
                <span className="tnum shrink-0 font-mono text-[10.5px] text-faint">
                  {h.incidents ?? 0} FIR{(h.incidents ?? 0) === 1 ? "" : "s"}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function Network() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const p = usePrincipal()
  const deps = [p?.role, p?.scope]

  const rings = useApi(() => api.rings(6), deps)
  const [focusId, setFocusId] = useState<string | null>(params.get("focus"))
  const [radius, setRadius] = useState(2)
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
    api.ego(activeId, radius).then((g) => {
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
  }, [activeId, radius, p?.role, p?.scope])

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
        <div className="flex w-full max-w-[560px] flex-col items-stretch gap-2 lg:items-end">
          <div className="flex w-full items-center gap-2">
            <EntitySearch onPick={(h) => setFocusId(h.canonical_id)} />
            <div
              className="ml-auto flex shrink-0 items-center gap-0.5 rounded-sm border border-line bg-panel p-0.5"
              role="group"
              aria-label="Trace depth in hops"
            >
              {[1, 2, 3].map((r) => (
                <button
                  key={r}
                  onClick={() => setRadius(r)}
                  className={cn(
                    "rounded-[3px] px-2 py-1 font-mono text-[10.5px] text-muted-foreground transition-colors",
                    radius === r && "bg-brass-soft text-brass",
                  )}
                  aria-pressed={radius === r}
                >
                  {r}-hop
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-1.5 lg:justify-end">
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
              {selected.id !== activeId && (
                <Button
                  size="sm"
                  className="w-full text-[11.5px]"
                  onClick={() => setFocusId(selected.id)}
                >
                  <Crosshair className="size-3.5" /> Trace from here
                </Button>
              )}
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
