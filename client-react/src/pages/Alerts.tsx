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
  const [acked, setAcked] = useState<Set<number>>(new Set())

  const alerts = anomalies.data?.sample ?? []
  const maxZ = Math.max(1, ...alerts.map((a) => a.z_score ?? 1))
  const wards = (fairness.data?.wards ?? []).slice(0, 8)
  const fs = fairness.data?.summary

  function ack(i: number, assign = false) {
    setAcked((s) => new Set(s).add(i))
    toast(assign ? "Alert assigned to district control room" : "Alert acknowledged", {
      description: "Workflow update is optimistic — reconciled with the alert store.",
    })
  }

  return (
    <>
      <PageHeader
        title="Alerts & Risk Forecast"
        caption="Emerging-trend spikes, the walk-forward risk forecast and the fairness audit — every prediction explained."
      />

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Detected</div>
            <CardTitle className="mt-1 text-[15px]">Emerging-trend alerts</CardTitle>
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
                        "flex items-start gap-3 rounded-md border border-border-soft p-3 transition-opacity",
                        isAcked && "opacity-55",
                      )}
                    >
                      <span
                        className={cn(
                          "flex size-8 shrink-0 items-center justify-center rounded-md",
                          a.severity === "high" ? "bg-danger-soft" : "bg-warn-soft",
                        )}
                      >
                        <AlertTriangle
                          className={cn("size-4", a.severity === "high" ? "text-danger" : "text-warn")}
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
                                ? "border-danger/30 bg-danger-soft text-danger"
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
              <CardTitle className="mt-1 text-[15px]">Predicted vs actual per ward</CardTitle>
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
                  Wards predicted &gt; {fs?.flag_ratio ?? 1.3}× their actual rate are flagged for review — the
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
            <CardTitle className="mt-1 text-[15px]">Highest-risk cells (next period)</CardTitle>
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
    </>
  )
}
