import { MessageSquareText } from "lucide-react"
import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"

import {
  EmptyState,
  Guardrail,
  MaskBadge,
  Notice,
  PageHeader,
  ReasonChip,
  RoleChip,
  ShimmerRows,
  entityIcon,
} from "@/components/common/bits"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { api } from "@/lib/api"
import { d10 } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"
import { upsertTab } from "@/lib/workspace"

export default function CaseFile() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const p = usePrincipal()
  const { data, error, loading } = useApi(() => api.caseFull(id), [id, p?.role, p?.scope])

  const inc = data?.incident
  useEffect(() => {
    if (id) upsertTab({ type: "case", id, title: inc?.fir_no || id })
  }, [id, inc?.fir_no])

  if (loading) return <ShimmerRows n={4} h={90} />

  if (error?.status === 403)
    return (
      <Notice title="Access restricted">
        {error.detail || "This case is outside your jurisdiction or role."} Current clearance:{" "}
        <b className="font-mono">{presetFor(p)?.label || p?.role}</b>. Switch role in the sidebar to
        compare access — the gate is enforced server-side.
      </Notice>
    )
  if (error || !inc)
    return (
      <Notice kind="error" title="Case not found">
        No FIR with id “{id}” exists in the canonical store.
      </Notice>
    )

  const underInv = String(inc.status || "").startsWith("Under")

  return (
    <>
      <PageHeader title={<span className="font-mono">{inc.fir_no || id}</span>} caption={inc.address_text}>
        <Button
          variant="outline"
          onClick={() =>
            navigate("/copilot", {
              state: { ask: `cases similar to ${inc.crime_type || ""} in ${inc.district_code || ""}` },
            })
          }
        >
          <MessageSquareText className="size-4" /> Ask copilot
        </Button>
      </PageHeader>

      <Card>
        <CardContent className="flex flex-wrap items-center gap-2 py-3.5">
          {inc.case_category && (
            <Badge variant="outline" className="font-mono text-muted-foreground">
              {inc.case_category}
            </Badge>
          )}
          <Badge variant="outline" className="border-info/30 bg-info-soft text-info">
            {inc.crime_type || "?"}
          </Badge>
          {inc.gravity === "Heinous" && (
            <Badge variant="outline" className="border-danger/30 bg-danger-soft text-danger">
              Heinous
            </Badge>
          )}
          <Badge variant="outline" className="font-mono text-muted-foreground">
            {inc.district_code || "?"} / {inc.station_code || "?"}
          </Badge>
          <Badge
            variant="outline"
            className={
              underInv
                ? "border-warn/30 bg-warn-soft text-warn"
                : "border-ok/30 bg-ok-soft text-ok"
            }
          >
            {inc.status || "status ?"}
          </Badge>
          {inc.ipc_bns_code && (
            <Badge variant="outline" className="font-mono text-muted-foreground">
              § {inc.ipc_bns_code}
            </Badge>
          )}
          {data?.chargesheet && (
            <Badge
              variant="outline"
              className={
                data.chargesheet.cs_type === "A"
                  ? "border-ok/30 bg-ok-soft text-ok"
                  : "border-danger/30 bg-danger-soft text-danger"
              }
            >
              {data.chargesheet.cs_type === "A"
                ? "Chargesheet filed"
                : data.chargesheet.cs_type === "B"
                  ? "False case"
                  : "Undetected"}
            </Badge>
          )}
          {data?.protected && <MaskBadge reason="IPC-228A/POCSO protected" />}
          {data?.series_id && (
            <Badge variant="outline" className="border-warn/30 bg-warn-soft font-mono text-warn">
              series {data.series_id}
            </Badge>
          )}
          <span className="ml-auto font-mono text-[11px] text-faint">
            occurred {d10(inc.occurred_at)}
            {inc.reported_at ? ` · reported ${d10(inc.reported_at)}` : ""}
          </span>
        </CardContent>
        {data?.officer && (
          <CardContent className="border-t py-2.5 text-[11.5px] text-muted-foreground">
            Registered by <b className="text-foreground">{data.officer.name}</b>
            {data.officer.rank ? ` · ${data.officer.rank}` : ""}
            {data.officer.designation ? ` · ${data.officer.designation}` : ""}
          </CardContent>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Parties</div>
            <CardTitle className="mt-1 text-[15px]">People, vehicles &amp; phones on this FIR</CardTitle>
          </CardHeader>
          <CardContent>
            {data.parties?.length ? (
              <div className="space-y-1.5">
                {data.parties.map((party, i) => {
                  const Icon = entityIcon(party.type)
                  const clickable = !!party.canonical_id
                  const Row = (
                    <>
                      <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border-soft bg-surface-2">
                        <Icon className="size-4 text-faint" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className={`block truncate text-[13px] ${party.type !== "person" ? "font-mono" : ""}`}>
                          {party.value} {party.masked && <MaskBadge reason={party.masked} />}
                        </span>
                        <span className="block truncate text-[11px] text-faint">
                          {[party.age && `age ${party.age}`, party.evidence_type && `evidence: ${party.evidence_type}`, party.note]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <RoleChip role={party.role} />
                    </>
                  )
                  return clickable ? (
                    <button
                      key={i}
                      onClick={() => navigate(`/entity/${encodeURIComponent(party.canonical_id!)}`)}
                      className="flex w-full items-center gap-3 rounded-md border border-transparent px-2 py-1.5 text-left transition-colors hover:border-border hover:bg-accent"
                    >
                      {Row}
                    </button>
                  ) : (
                    <div key={i} className="flex w-full items-center gap-3 px-2 py-1.5">
                      {Row}
                    </div>
                  )
                })}
              </div>
            ) : (
              <EmptyState>No parties recorded.</EmptyState>
            )}
            <Guardrail>
              Persons are as recorded in the FIR, pending investigation/trial. Victim/witness identity
              is masked outside the owning jurisdiction; IPC-228A/POCSO identities are masked for all
              but admin/case-officer.
            </Guardrail>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <div>
              <div className="k-label">Linked</div>
              <CardTitle className="mt-1 text-[15px]">Connected cases</CardTitle>
            </div>
            <Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">
              {data.linked_cases?.length ?? 0}
            </Badge>
          </CardHeader>
          <CardContent>
            {data.linked_cases?.length ? (
              <div className="space-y-2">
                {data.linked_cases.map((l) => (
                  <button
                    key={l.incident_id}
                    onClick={() => navigate(`/case/${encodeURIComponent(l.incident_id)}`)}
                    className="w-full rounded-md border border-border-soft p-2.5 text-left transition-colors hover:border-primary/40 hover:bg-accent"
                  >
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[12.5px] text-primary">{l.fir_no || l.incident_id}</span>
                      <Badge variant="outline" className="border-info/30 bg-info-soft text-[10px] text-info">
                        {l.crime_type}
                      </Badge>
                      <span className="font-mono text-[10.5px] text-faint">
                        {l.district_code} · {d10(l.occurred_at)}
                      </span>
                      <span className="ml-auto font-mono text-[10px] text-faint">link {l.strength}</span>
                    </span>
                    <span className="mt-1.5 flex flex-wrap gap-1">
                      {(l.reasons || []).map((r, j) => (
                        <ReasonChip key={j} type={r.type} detail={r.detail} />
                      ))}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState>
                No linked cases found — no shared entities, series membership or near-repeat pattern.
              </EmptyState>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <div className="k-label">Narrative</div>
            <CardTitle className="mt-1 text-[15px]">Brief facts / MO</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-[13px] leading-[1.7] text-muted-foreground">{inc.mo_text || "—"}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="k-label">Timeline</div>
            <CardTitle className="mt-1 text-[15px]">Case progression</CardTitle>
          </CardHeader>
          <CardContent>
            {data.timeline?.length ? (
              <div className="ml-1.5 space-y-4 border-l border-border pl-4">
                {data.timeline.map((t, i) => (
                  <div key={i} className="relative">
                    <span className="absolute -left-[21.5px] top-1 size-2.5 rounded-full border-2 border-primary bg-background" />
                    <div className="font-mono text-[11px] text-faint">{t.ts}</div>
                    <div className="text-[12.5px]">{t.label}</div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState>No status transitions recorded.</EmptyState>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  )
}
