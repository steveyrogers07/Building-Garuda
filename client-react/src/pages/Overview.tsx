import { Activity, ShieldCheck, Siren, Target, Users, Waypoints } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { EmptyState, KpiCard, MiniBar, PageHeader, ShimmerRows } from "@/components/common/bits"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { fmt } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"

export default function Overview() {
  const navigate = useNavigate()
  const p = usePrincipal()
  const deps = [p?.role, p?.scope]
  const stats = useApi(() => api.stats(), deps)
  const rings = useApi(() => api.rings(6), deps)
  const anomalies = useApi(() => api.anomalies(), deps)
  const fairness = useApi(() => api.fairness(), deps)

  const alerts = anomalies.data?.sample ?? []
  const ringRows = rings.data?.rings ?? []
  const crimes = stats.data?.by_crime ?? []
  const maxCrime = Math.max(1, ...crimes.map((c) => c[1]))
  const fs = fairness.data?.summary

  return (
    <>
      <PageHeader
        eyebrow="Command · Karnataka SCRB"
        title="Operations Overview"
        caption="Every tile drills into a case, an entity or the graph."
      >
        <Button onClick={() => navigate("/network")} className="t-display text-[14px] tracking-[0.1em]">
          <Waypoints className="size-4" /> Open network reveal
        </Button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard label="Incidents" value={fmt(stats.data?.incidents)} detail="tracked FIRs (canonical)" icon={Activity} />
        <KpiCard label="Entities" value={fmt(stats.data?.entities)} detail="persons · phones · vehicles" icon={Users} />
        <KpiCard label="Cross-district rings" value={rings.loading ? "-" : fmt(ringRows.length)} detail="organized networks surfaced" icon={Target} tone="accent" />
        <KpiCard label="Active alerts" value={anomalies.loading ? "-" : fmt(alerts.length)} detail="emerging-trend spikes" icon={Siren} tone="danger" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="k-label">Organized</div>
              <CardTitle className="t-display mt-1 text-[17px]">Cross-district rings</CardTitle>
            </div>
            <span className="font-mono text-[10px] text-faint">click → kingpin dossier</span>
          </CardHeader>
          <CardContent>
            {rings.loading ? (
              <ShimmerRows n={3} />
            ) : ringRows.length ? (
              <div className="space-y-1">
                {ringRows.map((r, i) => (
                  <button
                    key={r.kingpin_id}
                    onClick={() => navigate(`/entity/${encodeURIComponent(r.kingpin_id)}`)}
                    className="flex w-full items-center gap-3 rounded-sm border border-transparent px-2 py-2 text-left transition-colors hover:border-line hover:bg-accent"
                  >
                    {/* rank - rings are ordered by district span */}
                    <span className="t-display w-8 shrink-0 text-center text-[20px] leading-none text-brass">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[13px] font-medium">
                        {r.kingpin_label}
                        <span className="ml-2 font-mono text-[10.5px] text-faint">
                          {r.persons} members · shares {r.shared_links.join(", ")}
                        </span>
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[10.5px] text-faint">
                        {r.districts.join(" · ")}
                      </span>
                    </span>
                    <span className="stamp shrink-0 text-signal">
                      {r.district_count} districts
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState>No cross-district rings above threshold.</EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="k-label">Signals</div>
            <CardTitle className="t-display mt-1 text-[17px]">Emerging-trend alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {anomalies.loading ? (
              <ShimmerRows n={3} />
            ) : alerts.length ? (
              <div className="space-y-2.5">
                {alerts.slice(0, 5).map((a, i) => (
                  <div key={i} className="flex items-start gap-2.5 rounded-sm px-1 py-1">
                    <span
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        a.severity === "high" ? "bg-signal" : "bg-warn",
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[12.5px] font-medium">
                        {a.crime_type} · {a.district_code}
                      </div>
                      <div className="font-mono text-[10.5px] text-faint">
                        {a.window_start} · baseline ×{a.ratio ?? "?"}
                      </div>
                    </div>
                    <span
                      className={cn(
                        "font-mono text-[11px]",
                        a.severity === "high" ? "text-signal" : "text-warn",
                      )}
                    >
                      z {a.z_score ?? "?"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>No emerging-trend spikes right now.</EmptyState>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="k-label">Distribution</div>
          <CardTitle className="t-display mt-1 text-[17px]">Incidents by crime type</CardTitle>
        </CardHeader>
        <CardContent>
          {stats.loading ? (
            <ShimmerRows n={2} />
          ) : (
            <div className="space-y-2.5">
              {crimes.slice(0, 8).map(([name, count]) => (
                <div key={name} className="grid grid-cols-[170px_1fr_60px] items-center gap-3">
                  <span className="truncate text-[12.5px]">{name}</span>
                  <MiniBar value={count} max={maxCrime} />
                  <span className="tnum text-right font-mono text-[12px] text-muted-foreground">
                    {fmt(count)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <button
        onClick={() => navigate("/alerts")}
        className="flex w-full items-center gap-2.5 rounded-md border border-line-soft bg-panel px-4 py-2.5 text-left text-[11.5px] text-muted-foreground transition-colors hover:border-line hover:bg-accent"
      >
        <ShieldCheck className="size-4 shrink-0 text-ok" />
        <span className="min-w-0 flex-1 truncate">
          Forecast model <span className="font-mono">lgbm-p6-v1</span> · walk-forward validated · fairness
          audit {fs ? `flags ${fs.over_predicted ?? 0}/${fs.wards ?? "-"} wards for over-prediction review` : "active"} ·
          predictions target <b className="text-foreground">places &amp; times, never people</b>
        </span>
        <span className="font-mono text-[10px] text-faint">view →</span>
      </button>
    </>
  )
}
