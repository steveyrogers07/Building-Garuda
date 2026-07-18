import { FileText, Landmark, Search as SearchIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { EmptyState, PageHeader, ShimmerRows, entityIcon } from "@/components/common/bits"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { d10, fmt } from "@/lib/format"
import { usePrincipal } from "@/lib/roles"
import type { SearchResult } from "@/lib/types"
import { cn } from "@/lib/utils"

const FACETS = ["all", "cases", "people", "vehicles", "phones", "places", "narrative"] as const
type Facet = (typeof FACETS)[number]

export default function SearchPage() {
  const navigate = useNavigate()
  const p = usePrincipal()
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get("q") ?? "")
  const [facet, setFacet] = useState<Facet>("all")
  const [res, setRes] = useState<SearchResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const query = q.trim()
    if (query.length < 2) {
      setRes(null)
      return
    }
    setBusy(true)
    const t = setTimeout(() => {
      setParams({ q: query }, { replace: true })
      api
        .search(query)
        .then(setRes)
        .catch(() => setRes({ groups: {}, note: "Search unavailable for this role." }))
        .finally(() => setBusy(false))
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, p?.role, p?.scope])

  const g = res?.groups ?? {}
  const show = (f: Facet) => facet === "all" || facet === f

  function Section({ title, children, count }: { title: string; children: React.ReactNode; count: number }) {
    if (!count) return null
    return (
      <div>
        <div className="k-label mb-2">
          {title} <span className="text-faint">· {count}</span>
        </div>
        <div className="space-y-1.5">{children}</div>
      </div>
    )
  }

  const total =
    (g.cases?.length || 0) +
    (g.people?.length || 0) +
    (g.vehicles?.length || 0) +
    (g.phones?.length || 0) +
    (g.places?.length || 0) +
    (res?.semantic?.length || 0)

  return (
    <>
      <PageHeader
        eyebrow="Investigate · Structured + semantic"
        title="Universal Search"
        caption="Cases, people, vehicles, phones, places - structured + semantic over FIR narratives. Every search is audited."
      />

      <div className="mx-auto w-full max-w-3xl">
        <div className="relative">
          <SearchIcon className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-faint" />
          <Input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Try KA68MC3164 · +916534933629 · Aayush · “chain snatched near market”"
            className="h-11 bg-panel-2 pl-10 font-mono text-[13px]"
            aria-label="Universal search query"
          />
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {FACETS.map((f) => (
            <button
              key={f}
              onClick={() => setFacet(f)}
              className={cn(
                "rounded-sm border border-line bg-panel px-3 py-1 text-[11.5px] capitalize text-muted-foreground transition-colors hover:text-foreground",
                facet === f && "border-brass/50 bg-brass-soft text-brass",
              )}
            >
              {f}
            </button>
          ))}
          {res?.took_ms != null && (
            <span className="ml-auto self-center font-mono text-[10.5px] text-faint">{res.took_ms}ms</span>
          )}
        </div>

        <div className="mt-5 space-y-6">
          {q.trim().length < 2 ? (
            <EmptyState>
              Type at least two characters. Semantic search catches what keywords miss - try{" "}
              <i>“snatching fled on two-wheeler”</i>.
            </EmptyState>
          ) : busy && !res ? (
            <ShimmerRows n={4} />
          ) : total === 0 ? (
            <EmptyState>{res?.note || "No matches in the canonical store."}</EmptyState>
          ) : (
            <>
              {show("cases") && (
                <Section title="Cases" count={g.cases?.length || 0}>
                  {(g.cases || []).map((c) => (
                    <button
                      key={c.incident_id}
                      onClick={() => navigate(`/case/${encodeURIComponent(c.incident_id)}`)}
                      className="flex w-full items-center gap-3 rounded-md border border-line-soft bg-card px-3 py-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
                    >
                      <FileText className="size-4 shrink-0 text-faint" />
                      <span className="min-w-0 flex-1">
                        <span className="block font-mono text-[12.5px] text-brass">{c.fir_no || c.incident_id}</span>
                        <span className="block text-[11.5px] text-muted-foreground">
                          {c.crime_type} · {c.district_code} · {d10(c.occurred_at)}
                        </span>
                      </span>
                      <span className="text-[10.5px] text-faint">{c.status}</span>
                    </button>
                  ))}
                </Section>
              )}
              {(["people", "vehicles", "phones"] as const).map(
                (k) =>
                  show(k) && (
                    <Section key={k} title={k[0].toUpperCase() + k.slice(1)} count={g[k]?.length || 0}>
                      {(g[k] || []).map((e) => {
                        const Icon = entityIcon(e.type)
                        return (
                          <button
                            key={e.canonical_id}
                            onClick={() => navigate(`/entity/${encodeURIComponent(e.canonical_id)}`)}
                            className="flex w-full items-center gap-3 rounded-md border border-line-soft bg-card px-3 py-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
                          >
                            <Icon className="size-4 shrink-0 text-faint" />
                            <span className="min-w-0 flex-1">
                              <span className={cn("block text-[12.5px]", e.type !== "person" && "font-mono")}>
                                {e.value}
                                {e.masked && (
                                  <span className="ml-1.5 font-mono text-[10px] text-brass">
                                    [masked: {e.masked}]
                                  </span>
                                )}
                              </span>
                              <span className="block text-[11.5px] text-muted-foreground">
                                {fmt(e.incidents)} incidents · {(e.districts || []).join(" ")}
                              </span>
                            </span>
                            <span className="font-mono text-[10.5px] text-faint">{e.type}</span>
                          </button>
                        )
                      })}
                    </Section>
                  ),
              )}
              {show("places") && (
                <Section title="Places" count={g.places?.length || 0}>
                  {(g.places || []).map((pl) => (
                    <button
                      key={pl.code}
                      onClick={() => navigate("/map")}
                      className="flex w-full items-center gap-3 rounded-md border border-line-soft bg-card px-3 py-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
                    >
                      <Landmark className="size-4 shrink-0 text-faint" />
                      <span className="flex-1 font-mono text-[12.5px]">{pl.code}</span>
                      <span className="text-[11px] text-faint">{fmt(pl.incidents)} incidents</span>
                    </button>
                  ))}
                </Section>
              )}
              {show("narrative") && (
                <Section title="Narrative matches (semantic)" count={res?.semantic?.length || 0}>
                  {(res?.semantic || []).map((c) => (
                    <button
                      key={`s-${c.incident_id}`}
                      onClick={() => navigate(`/case/${encodeURIComponent(c.incident_id)}`)}
                      className="flex w-full items-center gap-3 rounded-md border border-line-soft bg-card px-3 py-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
                    >
                      <SearchIcon className="size-4 shrink-0 text-faint" />
                      <span className="min-w-0 flex-1">
                        <span className="block font-mono text-[12.5px] text-brass">{c.fir_no || c.incident_id}</span>
                        <span className="block truncate text-[11.5px] text-muted-foreground">
                          {(c.snippet || "").slice(0, 110)}…
                        </span>
                      </span>
                    </button>
                  ))}
                </Section>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}
