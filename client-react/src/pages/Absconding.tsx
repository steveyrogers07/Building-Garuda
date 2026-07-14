import { Flame, MapPinned, UserX, Users } from "lucide-react"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import {
  EmptyState,
  Guardrail,
  KpiCard,
  Notice,
  PageHeader,
  ShimmerRows,
} from "@/components/common/bits"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { api } from "@/lib/api"
import { fmt } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"

const MIN_DAYS = [
  { v: "0", label: "Any age" },
  { v: "90", label: "Open 90d+" },
  { v: "180", label: "Open 180d+" },
  { v: "365", label: "Open 1y+" },
]

/** §6 — suspects named on open FIRs with no arrest recorded, grouped by
 *  canonical person: the district's live "still out there" list and the seed
 *  for a watchlist/BOLO feature. Same derivation the A3 data gate proves. */
export default function Absconding() {
  const p = usePrincipal()
  const navigate = useNavigate()
  const [district, setDistrict] = useState("ALL")
  const [gravity, setGravity] = useState("ALL")
  const [minDays, setMinDays] = useState("0")

  const geo = useApi(() => api.geoDistricts(), [])
  const board = useApi(
    () =>
      api.absconding({
        district: district === "ALL" ? undefined : district,
        gravity: gravity === "ALL" ? undefined : gravity,
        minDays: Number(minDays) || undefined,
        limit: 60,
      }),
    [district, gravity, minDays, p?.role, p?.scope],
  )

  const scoped = p?.role === "district" || p?.role === "station"
  const b = board.data
  const s = b?.summary

  return (
    <>
      <PageHeader
        title="Absconding Board"
        caption="Suspects named on open FIRs with no arrest recorded — grouped by person, heinous cases first. The natural seed for watchlist/BOLO."
      >
        {!scoped && (
          <Select value={district} onValueChange={setDistrict}>
            <SelectTrigger className="w-[190px] bg-surface-2" aria-label="Filter district">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All districts</SelectItem>
              {(geo.data?.districts ?? []).map((d) => (
                <SelectItem key={d.code} value={d.code}>
                  {d.name || d.code} <span className="ml-1 font-mono text-faint">({d.code})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Select value={gravity} onValueChange={setGravity}>
          <SelectTrigger className="w-[150px] bg-surface-2" aria-label="Filter gravity">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">Any gravity</SelectItem>
            <SelectItem value="Heinous">Heinous</SelectItem>
            <SelectItem value="Non-Heinous">Non-Heinous</SelectItem>
          </SelectContent>
        </Select>
        <Select value={minDays} onValueChange={setMinDays}>
          <SelectTrigger className="w-[140px] bg-surface-2" aria-label="Filter case age">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MIN_DAYS.map((m) => (
              <SelectItem key={m.v} value={m.v}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PageHeader>

      {board.error?.status === 403 ? (
        <Notice title="Access restricted">
          {board.error.detail || "Case data is restricted for this role."} Current clearance:{" "}
          <b className="font-mono">{presetFor(p)?.label || p?.role}</b>.
        </Notice>
      ) : !b ? (
        board.loading ? <ShimmerRows n={4} h={90} /> : <EmptyState>Board unavailable.</EmptyState>
      ) : (
        <div
          className={cn(
            "space-y-5 transition-opacity duration-200",
            board.loading && "pointer-events-none opacity-60",
          )}
        >
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <KpiCard label="Wanted persons" value={fmt(s?.people)} detail="suspects with no arrest on an open case" icon={UserX} />
            <KpiCard
              label="Open case-pairs"
              value={fmt(s?.cases)}
              detail="person × open FIR combinations"
              icon={Users}
            />
            <KpiCard
              label="Involving heinous"
              value={fmt(s?.heinous_people)}
              detail="persons with ≥1 heinous open case"
              icon={Flame}
              tone={(s?.heinous_people ?? 0) > 0 ? "danger" : "default"}
            />
            <KpiCard label="Districts touched" value={fmt(s?.districts)} detail="jurisdictions with absconders" icon={MapPinned} />
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <div className="k-label">Board</div>
                <CardTitle className="mt-1 text-[15px]">
                  Heinous first · most open cases · longest at large
                </CardTitle>
              </div>
              <Badge variant="outline" className="font-mono text-[10px] text-faint">
                showing {Math.min(b.people.length, 60)} of {fmt(s?.people)} · as of {b.as_of}
              </Badge>
            </CardHeader>
            <CardContent>
              {b.people.length ? (
                <div className="space-y-2">
                  {b.people.map((per) => (
                    <div
                      key={per.canonical_id}
                      className="rounded-md border border-border-soft p-2.5 transition-colors hover:border-border"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => navigate(`/entity/${encodeURIComponent(per.canonical_id)}`)}
                          className="text-[13px] font-medium text-primary hover:underline"
                        >
                          {per.name}
                        </button>
                        {per.heinous && (
                          <Badge variant="outline" className="border-danger/30 bg-danger-soft text-[10px] text-danger">
                            Heinous
                          </Badge>
                        )}
                        <span className="font-mono text-[10.5px] text-faint">
                          {per.case_count} open {per.case_count === 1 ? "case" : "cases"} ·{" "}
                          {per.districts.join(" ")} · at large {fmt(per.max_days_open)}d
                        </span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {per.cases.map((c) => (
                          <button
                            key={c.incident_id}
                            onClick={() => navigate(`/case/${encodeURIComponent(c.incident_id)}`)}
                            title={`${c.crime_type} · ${c.status} · open ${c.days_open}d`}
                            className={`rounded border px-1.5 py-0.5 font-mono text-[10px] transition-colors hover:bg-accent ${
                              c.gravity === "Heinous"
                                ? "border-danger/30 bg-danger-soft text-danger"
                                : "border-border bg-surface-2 text-muted-foreground"
                            }`}
                          >
                            {c.fir_no || c.incident_id} · {c.crime_type}
                          </button>
                        ))}
                        {per.case_count > per.cases.length && (
                          <span className="px-1 py-0.5 text-[10px] text-faint">
                            +{per.case_count - per.cases.length} more
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState>No absconding accused match these filters.</EmptyState>
              )}
              <Guardrail>{b.guardrail}</Guardrail>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
