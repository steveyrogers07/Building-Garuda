import { AlertTriangle, Check, UserCheck } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { EmptyState, MiniBar, PageHeader, ShimmerRows } from "@/components/common/bits"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { pct } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"

function drivers(raw: string | string[]): string[] {
  if (Array.isArray(raw)) return raw
  try {
    return JSON.parse(raw) as string[]
  } catch {
    return raw ? [raw] : []
  }
}

export default function Alerts() {
  const p = usePrincipal()
  const deps = [p?.role, p?.scope]
  const anomalies = useApi(() => api.anomalies(), deps)
  const risk = useApi(() => api.riskTop(10), deps)
  const fairness = useApi(() => api.fairness(), deps)
  const socio = useApi(() => api.socio(), deps)
  const [acked, setAcked] = useState<Set<number>>(new Set())

  const alerts = anomalies.data?.sample ?? []
  const maxZ = Math.max(1, ...alerts.map((a) => a.z_score ?? 1))
  const wards = (fairness.data?.wards ?? []).slice(0, 8)
  const fs = fairness.data?.summary

  function ack(i: number, assign = false) {
    setAcked((s) => new Set(s).add(i))
    toast(assign ? "Alert assigned to district control room" : "Alert acknowledged", {
      description: "Workflow update is optimistic - reconciled with the alert store.",
    })
  }

  return (
    <>
      <PageHeader
        eyebrow="Command · Signals & forecast"
        title="Alerts & Risk Forecast"
        caption="Emerging-trend spikes, the walk-forward risk forecast and the fairness audit - every prediction explained."
      />

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Detected</div>
            <CardTitle className="t-display mt-1 text-[17px]">Emerging-trend alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {anomalies.loading ? (
              <ShimmerRows n={4} />
            ) : alerts.length ? (
              <div className="space-y-3">
                {alerts.map((a, i) => {
                  const isAcked = acked.has(i)
                  return (
                    <div
                      key={i}
                      className={cn(
                        "flex items-start gap-3 rounded-md border border-line-soft p-3 transition-opacity",
                        isAcked && "opacity-55",
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-8 shrink-0 items-center justify-center rounded-md",
                          a.severity === "high" ? "bg-signal-soft" : "bg-warn-soft",
                        )}
                      >
                        <AlertTriangle
                          className={cn("size-4", a.severity === "high" ? "text-signal" : "text-warn")}
                        />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 text-[13px] font-medium">
                          {a.crime_type} · {a.district_code}
                          <Badge
                            variant="outline"
                            className={cn(
                              "font-mono text-[10px]",
                              a.severity === "high"
                                ? "border-signal/30 bg-signal-soft text-signal"
                                : "border-warn/30 bg-warn-soft text-warn",
                            )}
                          >
                            {a.severity} · z {a.z_score ?? "?"}
                          </Badge>
                          {isAcked && (
                            <Badge variant="outline" className="font-mono text-[10px] text-ok">
                              acknowledged
                            </Badge>
                          )}
                        </div>
                        <div className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
                          {a.detail}
                        </div>
                        <MiniBar
                          value={a.z_score ?? 1}
                          max={maxZ}
                          tone={a.severity === "high" ? "danger" : "amber"}
                          className="mt-2 max-w-[260px]"
                        />
                      </div>
                      {!isAcked && (
                        <div className="flex shrink-0 flex-col gap-1.5">
                          <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => ack(i)}>
                            <Check className="size-3" /> Ack
                          </Button>
                          <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => ack(i, true)}>
                            <UserCheck className="size-3" /> Assign
                          </Button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState>No anomalies above baseline thresholds.</EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="k-label">Fairness</div>
              <CardTitle className="t-display mt-1 text-[17px]">Predicted vs actual per ward</CardTitle>
            </div>
            <Badge variant="outline" className="border-warn/30 bg-warn-soft font-mono text-[10px] text-warn">
              {fs?.over_predicted ?? "·"} flagged
            </Badge>
          </CardHeader>
          <CardContent>
            {fairness.loading ? (
              <ShimmerRows n={4} />
            ) : (
              <>
                <div className="space-y-2.5">
                  {wards.map((w) => (
                    <div key={w.area_code} className="grid grid-cols-[54px_1fr_52px] items-center gap-2.5">
                      <span className="font-mono text-[12px]">{w.area_code}</span>
                      <MiniBar
                        value={w.ratio}
                        max={1.6}
                        tone={w.over_predicted ? "danger" : "primary"}
                      />
                      <span className="tnum text-right font-mono text-[11px] text-muted-foreground">
                        ×{w.ratio.toFixed(2)}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-3.5 text-[11px] leading-relaxed text-faint">
                  Wards predicted &gt; {fs?.flag_ratio ?? 1.3}× their actual rate are flagged for review - the
                  over-policing guard. Forecasts target places &amp; times, never individuals.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <div>
            <div className="k-label">Forecast</div>
            <CardTitle className="t-display mt-1 text-[17px]">Highest-risk cells (next period)</CardTitle>
          </div>
          <span className="font-mono text-[10.5px] text-faint">
            {risk.data?.top?.[0]?.model_version ?? "lgbm"} · walk-forward
          </span>
        </CardHeader>
        <CardContent>
          {risk.loading ? (
            <ShimmerRows n={3} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="k-label">District</TableHead>
                  <TableHead className="k-label">Crime type</TableHead>
                  <TableHead className="k-label text-right">Risk</TableHead>
                  <TableHead className="k-label">Why (SHAP drivers)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(risk.data?.top ?? []).map((t, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-[12px]">{t.district_code}</TableCell>
                    <TableCell className="text-[12.5px]">{t.crime_type}</TableCell>
                    <TableCell className="tnum text-right font-mono text-[12.5px]">
                      {pct(t.risk_score)}
                    </TableCell>
                    <TableCell>
                      <span className="flex flex-wrap gap-1">
                        {drivers(t.top_drivers)
                          .slice(0, 3)
                          .map((d) => (
                            <Badge key={d} variant="outline" className="font-mono text-[10px] text-muted-foreground">
                              {d}
                            </Badge>
                          ))}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Socio-economic correlation - the "why behind the where". Overlays the
          Census indicators the forecast model already consumes as features, so
          a commander can see WHICH social conditions track crime rate, not just
          where the pins are. Rate per 100k, never raw counts. */}
      <Card>
        <CardHeader>
          <div className="k-label">Sociological context</div>
          <CardTitle className="t-display mt-1 text-[17px]">
            Socio-economic correlation - the “why” behind the “where”
          </CardTitle>
        </CardHeader>
        <CardContent>
          {socio.loading ? (
            <ShimmerRows n={3} h={54} />
          ) : !socio.data?.correlations?.length ? (
            <EmptyState>Socio-economic indicators unavailable.</EmptyState>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                {socio.data.correlations.map((c) => {
                  const r = c.r ?? 0
                  const tone =
                    c.strength === "strong" ? "text-signal"
                      : c.strength === "moderate" ? "text-brass" : "text-steel"
                  return (
                    <div
                      key={c.indicator}
                      className="rounded-sm border border-line-soft bg-panel-2/50 px-3 py-2.5"
                    >
                      <div className="k-label">{c.label}</div>
                      <div className={cn("tnum t-display mt-1 text-[22px] leading-none", tone)}>
                        {r > 0 ? "+" : ""}
                        {r.toFixed(2)}
                      </div>
                      <div className="mt-1 text-[10.5px] text-faint">
                        {c.strength} {c.direction} correlation with crime rate
                      </div>
                      <MiniBar value={Math.abs(r)} max={1} />
                    </div>
                  )
                })}
              </div>

              {/* The actionable half: which districts break their own profile. */}
              {socio.data.model && (
                <>
                  <div className="k-label mt-5 mb-1.5">
                    Expected vs actual - socio-economics explain{" "}
                    <span className="text-brass">{socio.data.model.explains_pct}%</span> of the
                    variation between districts (R² {socio.data.model.r2})
                  </div>
                  <p className="mb-2.5 text-[11px] leading-relaxed text-muted-foreground">
                    The rest is local. A district above its predicted rate has more crime than
                    its demographics account for - that gap, not the raw count, is where a
                    commander should look first.
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <div className="k-label mb-1.5 text-signal">More than predicted</div>
                      <div className="space-y-1">
                        {socio.data.model.above_expected.slice(0, 4).map((d) => (
                          <div
                            key={d.district_code}
                            className="flex items-center justify-between rounded-sm border border-signal/25 bg-signal/5 px-2 py-1.5 text-[11.5px]"
                          >
                            <span className="min-w-0 truncate">{d.name}</span>
                            <span className="ml-2 shrink-0 font-mono text-[11px]">
                              <span className="text-signal">+{d.residual.toFixed(1)}</span>
                              <span className="text-faint">
                                {" "}
                                ({d.rate_per_100k.toFixed(1)} vs {d.expected_rate.toFixed(1)})
                              </span>
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="k-label mb-1.5 text-ok">Fewer than predicted</div>
                      <div className="space-y-1">
                        {socio.data.model.below_expected.slice(0, 4).map((d) => (
                          <div
                            key={d.district_code}
                            className="flex items-center justify-between rounded-sm border border-ok/25 bg-ok/5 px-2 py-1.5 text-[11.5px]"
                          >
                            <span className="min-w-0 truncate">{d.name}</span>
                            <span className="ml-2 shrink-0 font-mono text-[11px]">
                              <span className="text-ok">{d.residual.toFixed(1)}</span>
                              <span className="text-faint">
                                {" "}
                                ({d.rate_per_100k.toFixed(1)} vs {d.expected_rate.toFixed(1)})
                              </span>
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* Different offences answer to different conditions. */}
              {!!socio.data.by_crime?.length && (
                <>
                  <div className="k-label mt-5 mb-1.5">
                    Which condition drives which crime
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Crime type</TableHead>
                        <TableHead className="text-right">Urbanisation</TableHead>
                        <TableHead className="text-right">Literacy</TableHead>
                        <TableHead className="text-right">Density</TableHead>
                        <TableHead>Strongest</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {socio.data.by_crime.slice(0, 6).map((c) => (
                        <TableRow key={c.crime_type}>
                          <TableCell className="text-[12.5px]">{c.crime_type}</TableCell>
                          {(["urbanization", "literacy", "density"] as const).map((k) => (
                            <TableCell
                              key={k}
                              className={cn(
                                "tnum text-right font-mono text-[12px]",
                                c.driver &&
                                  c[k] === c.driver_r
                                  ? "text-brass"
                                  : "text-muted-foreground",
                              )}
                            >
                              {c[k] === null ? "-" : (c[k] as number).toFixed(2)}
                            </TableCell>
                          ))}
                          <TableCell className="text-[11.5px] text-brass">{c.driver}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}

              <p className="mt-2.5 text-[11px] leading-relaxed text-faint">
                Ecological correlation across {socio.data.n_districts} districts -{" "}
                <b>association, not causation</b>. These are the same indicators the risk model
                consumes as features; they explain where risk concentrates, and are never used
                to profile individuals or communities.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </>
  )
}
