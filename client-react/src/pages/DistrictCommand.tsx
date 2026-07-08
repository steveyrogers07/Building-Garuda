import { AlertTriangle, ShieldCheck, Trophy } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { EmptyState, KpiCard, MiniBar, Notice, PageHeader, ShimmerRows } from "@/components/common/bits"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { fmt, pct } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"
import type { DistrictCommandCard } from "@/lib/types"

/** SP's cockpit for one district — load, backlog aging, and the clearance rate
 *  computed from ChargesheetDetails.cs_type (A/B/C), a metric the organizer
 *  schema carries but nobody else in the dataset was computing (blueprint §B1). */
export default function DistrictCommand() {
  const p = usePrincipal()
  const navigate = useNavigate()
  const homeDistrict = p?.role === "district" || p?.role === "station" ? p.scope.slice(0, 3) : ""
  const [code, setCode] = useState(homeDistrict || "BNU")

  const geo = useApi(() => api.geoDistricts(), [])
  const card = useApi(() => api.districtCommand(code), [code, p?.role, p?.scope])
  const rank = useApi(() => api.districtRank(), [p?.role, p?.scope])

  const districts = geo.data?.districts ?? []
  useEffect(() => {
    if (!homeDistrict && districts.length && !districts.some((d) => d.code === code)) {
      setCode(districts[0].code)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districts])

  const c = card.data as DistrictCommandCard | undefined
  const maxCrime = Math.max(1, ...(c?.top_crimes ?? []).map(([, n]) => n))
  const maxCases = Math.max(1, ...(c?.top_officers ?? []).map((o) => o.cases))

  return (
    <>
      <PageHeader
        title="District Command"
        caption="Load, backlog aging, and the clearance & conviction rate from chargesheet outcomes — the metric nobody else computes."
      >
        {!homeDistrict && (
          <Select value={code} onValueChange={setCode}>
            <SelectTrigger className="w-[220px] bg-surface-2" aria-label="Select district">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {districts.map((d) => (
                <SelectItem key={d.code} value={d.code}>
                  {d.name || d.code} <span className="ml-1 font-mono text-faint">({d.code})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </PageHeader>

      {card.loading ? (
        <ShimmerRows n={4} h={90} />
      ) : card.error?.status === 403 ? (
        <Notice title="Access restricted">
          {card.error.detail || "This district is outside your jurisdiction."} Current clearance:{" "}
          <b className="font-mono">{presetFor(p)?.label || p?.role}</b>.
        </Notice>
      ) : !c ? (
        <EmptyState>No command data for this district.</EmptyState>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <KpiCard label="Total incidents" value={fmt(c.total_incidents)} detail={`${c.district_code} · all recorded FIRs`} />
            <KpiCard
              label="Clearance rate"
              value={c.clearance_rate == null ? "–" : pct(c.clearance_rate)}
              detail={`${fmt(c.outcomes.A)} chargesheeted / ${fmt(c.outcomes_total)} disposed`}
              icon={ShieldCheck}
              tone="accent"
            />
            <KpiCard label="Open cases" value={fmt(c.open)} detail={`${fmt(c.disposed)} disposed`} />
            <KpiCard
              label="Backlog aging"
              value={fmt(c.backlog_aging)}
              detail={`open > ${c.backlog_threshold_days}d since occurrence`}
              icon={AlertTriangle}
              tone={c.backlog_aging > 0 ? "danger" : "default"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1fr_1.3fr]">
            <Card>
              <CardHeader>
                <div className="k-label">Outcomes</div>
                <CardTitle className="mt-1 text-[15px]">Final-report breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                {c.outcomes_total ? (
                  <div className="space-y-3">
                    {([
                      ["A", "Chargesheet filed", c.outcomes.A, "primary"],
                      ["B", "False case", c.outcomes.B, "amber"],
                      ["C", "Undetected", c.outcomes.C, "danger"],
                    ] as const).map(([k, label, n, tone]) => (
                      <div key={k} className="grid grid-cols-[110px_1fr_50px] items-center gap-3">
                        <span className="text-[12.5px]">{label}</span>
                        <MiniBar value={n} max={c.outcomes_total} tone={tone} />
                        <span className="tnum text-right font-mono text-[12px] text-muted-foreground">{fmt(n)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>No chargesheets filed yet for this district's cases.</EmptyState>
                )}
                <p className="mt-3.5 text-[11px] leading-relaxed text-faint">
                  cstype from ChargesheetDetails: A=Chargesheet, B=False Case, C=Undetected. Clearance
                  rate = A / (A+B+C). Only terminal-status cases carry a final report.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="k-label">Distribution</div>
                <CardTitle className="mt-1 text-[15px]">Top crime types</CardTitle>
              </CardHeader>
              <CardContent>
                {c.top_crimes.length ? (
                  <div className="space-y-2.5">
                    {c.top_crimes.map(([name, n]) => (
                      <div key={name} className="grid grid-cols-[170px_1fr_60px] items-center gap-3">
                        <span className="truncate text-[12.5px]">{name}</span>
                        <MiniBar value={n} max={maxCrime} />
                        <span className="tnum text-right font-mono text-[12px] text-muted-foreground">{fmt(n)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState>No incidents recorded.</EmptyState>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <div className="k-label">Officers</div>
                <CardTitle className="mt-1 text-[15px]">Case load &amp; clearance by officer</CardTitle>
              </div>
              <Badge variant="outline" className="font-mono text-[10px] text-faint">
                D3 · staff the case with proven hands
              </Badge>
            </CardHeader>
            <CardContent>
              {c.top_officers.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="k-label">Officer</TableHead>
                      <TableHead className="k-label">Rank</TableHead>
                      <TableHead className="k-label text-right">Cases</TableHead>
                      <TableHead className="k-label">Load</TableHead>
                      <TableHead className="k-label text-right">Chargesheeted</TableHead>
                      <TableHead className="k-label text-right">Clearance</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {c.top_officers.map((o) => (
                      <TableRow key={o.officer_id}>
                        <TableCell className="text-[12.5px]">{o.name}</TableCell>
                        <TableCell className="font-mono text-[11.5px] text-muted-foreground">{o.rank}</TableCell>
                        <TableCell className="tnum text-right font-mono text-[12px]">{o.cases}</TableCell>
                        <TableCell><MiniBar value={o.cases} max={maxCases} className="max-w-[120px]" /></TableCell>
                        <TableCell className="tnum text-right font-mono text-[12px]">{o.chargesheeted}</TableCell>
                        <TableCell className="tnum text-right font-mono text-[12px] text-amber">
                          {o.clearance_rate == null ? "–" : pct(o.clearance_rate)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState>No officers assigned in this district yet.</EmptyState>
              )}
            </CardContent>
          </Card>

          {!rank.loading && !rank.error && (rank.data?.districts?.length ?? 0) > 0 && (
            <Card>
              <CardHeader className="flex-row items-center justify-between space-y-0">
                <div>
                  <div className="k-label">Statewide</div>
                  <CardTitle className="mt-1 text-[15px]">District ranking by clearance rate</CardTitle>
                </div>
                <Trophy className="size-4 text-amber" />
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 md:grid-cols-3">
                  {(rank.data?.districts ?? []).map((d, i) => (
                    <button
                      key={d.district_code}
                      onClick={() => setCode(d.district_code)}
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-accent"
                    >
                      <span className="w-5 font-mono text-[11px] text-faint">{i + 1}</span>
                      <span className="w-9 font-mono text-[12px] font-medium">{d.district_code}</span>
                      <MiniBar value={d.clearance_rate ?? 0} max={1} className="flex-1" tone="amber" />
                      <span className="tnum w-12 text-right font-mono text-[11.5px] text-muted-foreground">
                        {d.clearance_rate == null ? "–" : pct(d.clearance_rate)}
                      </span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          <button
            onClick={() => navigate("/copilot", { state: { ask: `crime in ${c.district_code}` } })}
            className="text-left text-[11.5px] text-faint hover:text-muted-foreground"
          >
            Ask copilot about {c.district_code} →
          </button>
        </>
      )}
    </>
  )
}
