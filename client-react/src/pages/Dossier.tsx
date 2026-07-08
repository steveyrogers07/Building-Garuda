import { MessageSquareText, Waypoints } from "lucide-react"
import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"

import {
  EmptyState,
  Guardrail,
  MaskBadge,
  MiniBar,
  Notice,
  ShimmerRows,
  entityIcon,
} from "@/components/common/bits"
import { RoleChip } from "@/components/common/bits"
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
import { d10, fmt } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"
import { upsertTab } from "@/lib/workspace"

export default function Dossier() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const p = usePrincipal()
  const { data: d, error, loading } = useApi(() => api.entity(id), [id, p?.role, p?.scope])

  useEffect(() => {
    if (id) upsertTab({ type: "entity", id, title: d?.value || id, icon: d?.type })
  }, [id, d?.value, d?.type])

  if (loading) return <ShimmerRows n={4} h={90} />

  if (error?.status === 403)
    return (
      <Notice title="Access restricted">
        {error.detail || "Dossiers are not available to this role."} Current clearance:{" "}
        <b className="font-mono">{presetFor(p)?.label || p?.role}</b>. Switch role in the sidebar to
        compare access.
      </Notice>
    )
  if (error || !d)
    return (
      <Notice kind="error" title="Entity not found">
        No entity “{id}” in the canonical store.
      </Notice>
    )

  const Icon = entityIcon(d.type)
  const s = d.stats || {}
  const maxW = Math.max(1, ...(d.associates || []).map((a) => a.weight || 1))
  const months = d.timeline || []
  const maxM = Math.max(1, ...months.map((m) => m.count))

  return (
    <>
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex size-12 shrink-0 items-center justify-center rounded-lg border border-amber/30 bg-amber-soft">
              <Icon className="size-6 text-amber" />
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="flex flex-wrap items-center gap-2 text-[19px] font-semibold">
                <span className={d.type !== "person" ? "font-mono" : ""}>{d.value}</span>
                {d.masked && <MaskBadge reason={`masked · ${d.masked}`} />}
              </h2>
              <div className="mt-0.5 font-mono text-[11.5px] text-faint">
                {d.type} · {d.canonical_id}
                {(d.aliases || []).length > 0 && (
                  <>
                    {" · aka "}
                    {(d.aliases || []).map((a, i) => (
                      <span key={i} className="mr-1 rounded border border-border-soft bg-surface-2 px-1 py-px">
                        {a.value}
                      </span>
                    ))}
                  </>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => navigate(`/network?focus=${encodeURIComponent(d.canonical_id)}`)}>
                <Waypoints className="size-3.5" /> Ego network
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate("/copilot", { state: { ask: `incidents involving ${d.value}` } })}
              >
                <MessageSquareText className="size-3.5" /> Ask copilot
              </Button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 border-t pt-4 sm:grid-cols-5">
            {[
              ["Incidents", fmt(s.incidents)],
              ["Districts", String((s.districts || []).length)],
              ["First seen", s.first_seen || "–"],
              ["Last seen", s.last_seen || "–"],
              ["Reach", (s.districts || []).join(" ") || "–"],
            ].map(([k, v]) => (
              <div key={k}>
                <div className="k-label">{k}</div>
                <div className="tnum mt-1 font-mono text-[14px] font-semibold">{v}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Record</div>
            <CardTitle className="mt-1 text-[15px]">Appearances across FIRs</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[420px] overflow-auto">
            {(d.appearances || []).length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="k-label">FIR</TableHead>
                    <TableHead className="k-label">Role</TableHead>
                    <TableHead className="k-label">Crime</TableHead>
                    <TableHead className="k-label">District</TableHead>
                    <TableHead className="k-label">Date</TableHead>
                    <TableHead className="k-label">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(d.appearances || []).map((a, i) => (
                    <TableRow
                      key={i}
                      className="cursor-pointer"
                      onClick={() => navigate(`/case/${encodeURIComponent(a.incident_id)}`)}
                    >
                      <TableCell className="font-mono text-[12px] text-primary">{a.fir_no || a.incident_id}</TableCell>
                      <TableCell><RoleChip role={a.role} /></TableCell>
                      <TableCell className="text-[12px]">{a.crime_type || ""}</TableCell>
                      <TableCell className="font-mono text-[12px]">{a.district_code || ""}</TableCell>
                      <TableCell className="font-mono text-[12px]">{d10(a.occurred_at)}</TableCell>
                      <TableCell className="text-[11px] text-faint">{a.status || ""}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <EmptyState>No recorded appearances.</EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="k-label">Network</div>
              <CardTitle className="mt-1 text-[15px]">Known associates</CardTitle>
            </div>
            <span className="font-mono text-[10px] text-faint">co-occurrence</span>
          </CardHeader>
          <CardContent>
            {(d.associates || []).length ? (
              <div className="space-y-1.5">
                {(d.associates || []).map((a) => {
                  const AIcon = entityIcon(a.type)
                  return (
                    <button
                      key={a.canonical_id}
                      onClick={() => navigate(`/entity/${encodeURIComponent(a.canonical_id)}`)}
                      className="flex w-full items-center gap-3 rounded-md border border-transparent px-2 py-1.5 text-left transition-colors hover:border-border hover:bg-accent"
                    >
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border-soft bg-surface-2">
                        <AIcon className="size-4 text-faint" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className={`block truncate text-[12.5px] ${a.type !== "person" ? "font-mono" : ""}`}>
                          {a.label} {a.masked && <MaskBadge reason={a.masked} />}
                        </span>
                        <MiniBar value={a.weight || 1} max={maxW} className="mt-1.5 max-w-[170px]" />
                      </span>
                      <span className="text-right">
                        <span className="tnum font-mono text-[12px]">{a.weight}×</span>
                        <span className="block text-[9.5px] text-faint">{(a.kinds || []).join(", ")}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
            ) : (
              <EmptyState>No co-occurring entities.</EmptyState>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Temporal</div>
            <CardTitle className="mt-1 text-[15px]">Activity timeline</CardTitle>
          </CardHeader>
          <CardContent>
            {months.length ? (
              <>
                <div className="flex h-[120px] items-end gap-1.5">
                  {months.map((m) => (
                    <div
                      key={m.month}
                      title={`${m.month}: ${m.count}`}
                      className="flex-1 rounded-t-sm bg-primary/70 transition-colors hover:bg-amber"
                      style={{ height: `${Math.max(8, (100 * m.count) / maxM)}%` }}
                    />
                  ))}
                </div>
                <div className="mt-1.5 flex justify-between font-mono text-[10px] text-faint">
                  <span>{months[0]?.month}</span>
                  <span>{months[months.length - 1]?.month}</span>
                </div>
              </>
            ) : (
              <EmptyState>No temporal activity.</EmptyState>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="k-label">Assessment</div>
            <CardTitle className="mt-1 text-[15px]">Activity indicators</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[12.5px]">
              <span className="k-label">recorded incidents</span>
              <span className="tnum font-mono">{fmt(d.indicators?.incident_count)}</span>
              <span className="k-label">district span</span>
              <span className="tnum font-mono">{fmt(d.indicators?.district_span)}</span>
              <span className="k-label">peak month</span>
              <span className="tnum font-mono">{fmt(d.indicators?.active_month_max)} incidents</span>
              <span className="k-label">role mix</span>
              <span className="font-mono text-[11px]">
                {Object.entries(s.roles || {})
                  .map(([k, v]) => `${k}:${v}`)
                  .join("  ") || "–"}
              </span>
            </div>
            {d.guardrail && <Guardrail>{d.guardrail}</Guardrail>}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
