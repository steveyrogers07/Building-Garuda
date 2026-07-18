import { MessageSquareText } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import {
  DeadlineBadge,
  EmptyState,
  Guardrail,
  MaskBadge,
  Notice,
  PageHeader,
  ReasonChip,
  ShimmerRows,
  Stamp,
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

/** Party-role stamp on the paper sheet - suspects in beacon red, the rest in
 *  registrar's ink, exactly as an FIR reads. */
function PaperRole({ role }: { role: string }) {
  const hot = role === "suspect" || role === "accused"
  return (
    <Stamp onPaper tone={hot ? "signal" : "dim"} className="shrink-0">
      {role}
    </Stamp>
  )
}

export default function CaseFile() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const p = usePrincipal()
  const { data, error, loading } = useApi(() => api.caseFull(id), [id, p?.role, p?.scope])

  const inc = data?.incident
  const [scanState, setScanState] = useState<"loading" | "ok" | "missing">("loading")
  useEffect(() => setScanState("loading"), [id])
  useEffect(() => {
    if (id) upsertTab({ type: "case", id, title: inc?.fir_no || id })
  }, [id, inc?.fir_no])

  if (loading) return <ShimmerRows n={4} h={90} />

  if (error?.status === 403)
    return (
      <Notice title="Access restricted">
        {error.detail || "This case is outside your jurisdiction or role."} Current clearance:{" "}
        <b className="font-mono">{presetFor(p)?.label || p?.role}</b>. Switch role in the sidebar to
        compare access - the gate is enforced server-side.
      </Notice>
    )
  if (error || !inc)
    return (
      <Notice kind="error" title="Case not found">
        No FIR with id “{id}” exists in the canonical store.
      </Notice>
    )

  const underInv = String(inc.status || "").startsWith("Under")
  const cs = data?.chargesheet

  return (
    <>
      <PageHeader
        eyebrow="Case file · Source document + derived intelligence"
        title={<span className="tnum">{inc.fir_no || id}</span>}
        caption={inc.address_text}
      >
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

      <div className="grid items-start gap-5 lg:grid-cols-[1.35fr_1fr]">
        {/* ── the FIR itself - manila paper pulled onto the desk ─────────── */}
        <div className="paper-sheet relative overflow-hidden rounded-sm">
          <div className="paper-edge absolute inset-y-0 left-0 w-7 border-r border-paper-line/60" />
          <div className="py-5 pl-11 pr-6">
            {/* register head */}
            <div className="flex flex-wrap items-start justify-between gap-3 border-b-2 border-paper-ink/70 pb-3">
              <div>
                <div className="k-label-paper">First Information Report · Karnataka State Police</div>
                <div className="t-display mt-1 text-[24px] leading-none text-paper-ink">
                  {inc.fir_no || id}
                </div>
                <div className="mt-1 font-mono text-[11px] text-paper-dim">
                  {inc.district_code || "?"} / {inc.station_code || "?"} · occurred {d10(inc.occurred_at)}
                  {inc.reported_at ? ` · reported ${d10(inc.reported_at)}` : ""}
                </div>
                {inc.crime_no && (
                  <div className="mt-0.5 font-mono text-[11px] tracking-wide text-paper-dim">
                    Crime No <b className="text-paper-ink">{inc.crime_no}</b>
                    {inc.case_no ? ` · Case No ${inc.case_no}` : ""}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap justify-end gap-1.5">
                {inc.case_category && <Stamp onPaper tone="dim">{inc.case_category}</Stamp>}
                {inc.gravity === "Heinous" && <Stamp onPaper tone="signal">Heinous</Stamp>}
                <Stamp onPaper tone={underInv ? "warn" : "ok"}>{inc.status || "status ?"}</Stamp>
                {cs && (
                  <Stamp onPaper tone={cs.cs_type === "A" ? "ok" : "signal"}>
                    {cs.cs_type === "A" ? "Chargesheet filed" : cs.cs_type === "B" ? "False case" : "Undetected"}
                  </Stamp>
                )}
              </div>
            </div>

            {/* offence line */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-paper-line py-2.5 text-[12.5px] text-paper-ink">
              <span className="font-medium">{inc.crime_type || "?"}</span>
              {inc.ipc_bns_code && <span className="font-mono text-[11.5px] text-paper-dim">§ {inc.ipc_bns_code}</span>}
              {data?.series_id && (
                <span className="font-mono text-[11px] text-paper-dim">series {data.series_id}</span>
              )}
              {data?.protected && <MaskBadge onPaper reason="IPC-228A/POCSO protected" />}
              {data?.officer && (
                <span className="ml-auto text-[11.5px] text-paper-dim">
                  Registered by <b className="text-paper-ink">{data.officer.name}</b>
                  {data.officer.rank ? ` · ${data.officer.rank}` : ""}
                </span>
              )}
            </div>

            {/* parties */}
            <div className="py-3">
              <div className="k-label-paper mb-2">Parties on record</div>
              {data.parties?.length ? (
                <div className="divide-y divide-paper-line/70">
                  {data.parties.map((party, i) => {
                    const Icon = entityIcon(party.type)
                    const clickable = !!party.canonical_id
                    const Row = (
                      <>
                        <Icon className="size-4 shrink-0 text-paper-faint" />
                        <span className="min-w-0 flex-1">
                          <span
                            className={`block truncate text-[13px] text-paper-ink ${party.type !== "person" ? "font-mono text-[12.5px]" : ""}`}
                          >
                            {party.value} {party.masked && <MaskBadge onPaper reason={party.masked} />}
                          </span>
                          <span className="block truncate text-[11px] text-paper-dim">
                            {[party.age && `age ${party.age}`, party.evidence_type && `evidence: ${party.evidence_type}`, party.note]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                        <PaperRole role={party.role} />
                      </>
                    )
                    return clickable ? (
                      <button
                        key={i}
                        onClick={() => navigate(`/entity/${encodeURIComponent(party.canonical_id!)}`)}
                        className="flex w-full items-center gap-3 px-1 py-2 text-left transition-colors hover:bg-paper-2"
                      >
                        {Row}
                      </button>
                    ) : (
                      <div key={i} className="flex w-full items-center gap-3 px-1 py-2">
                        {Row}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="py-4 text-center text-[12px] text-paper-faint">No parties recorded.</div>
              )}
            </div>

            {/* narrative */}
            <div className="border-t border-paper-line pt-3">
              <div className="k-label-paper mb-1.5">Brief facts / MO</div>
              <p className="text-[13px] leading-[1.75] text-paper-ink/90">{inc.mo_text || "-"}</p>
            </div>
          </div>
        </div>

        {/* ── derived intelligence - stays on the console ────────────────── */}
        <div className="space-y-4">
          {underInv && !cs && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-panel px-3.5 py-2.5 shadow-panel">
              <div className="min-w-0">
                <div className="k-label">Derived · Default-bail clock</div>
                <div className="mt-1 text-[11.5px] text-muted-foreground">
                  {data.deadline
                    ? `Chargesheet due ${data.deadline.due_date} - ${data.deadline.window_days}d window from first arrest (${data.deadline.arrest_date})`
                    : "No clock running - nobody arrested on this case yet (CrPC 167(2)/BNSS 187)."}
                </div>
              </div>
              <DeadlineBadge deadline={data.deadline} verbose />
            </div>
          )}
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <div className="k-label">Derived · Linked</div>
                <CardTitle className="t-display mt-1 text-[17px]">Connected cases</CardTitle>
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
                      className="w-full rounded-sm border border-line-soft p-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
                    >
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[12.5px] text-brass">{l.fir_no || l.incident_id}</span>
                        <span className="text-[11px] text-muted-foreground">{l.crime_type}</span>
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
                  No linked cases found - no shared entities, series membership or near-repeat pattern.
                </EmptyState>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="k-label">Derived · Timeline</div>
              <CardTitle className="t-display mt-1 text-[17px]">Case progression</CardTitle>
            </CardHeader>
            <CardContent>
              {data.timeline?.length ? (
                <div className="ml-1.5 space-y-4 border-l border-line pl-4">
                  {data.timeline.map((t, i) => (
                    <div key={i} className="relative">
                      <span className="absolute -left-[21.5px] top-1 size-2.5 rounded-full border-2 border-brass bg-background" />
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

          {/* provenance: the scanned source document behind this record (local
              renders now; the Stratus raw-fir bucket in prod). Hidden when no
              scan exists - only a sample of the corpus has rendered documents. */}
          {scanState !== "missing" && (
            <Card>
              <CardHeader>
                <div className="k-label">Provenance</div>
                <CardTitle className="t-display mt-1 text-[17px]">Source FIR - scanned original</CardTitle>
              </CardHeader>
              <CardContent>
                <img
                  src={`/fir/${encodeURIComponent(id || "")}`}
                  alt={`Scanned FIR document for ${inc.fir_no || id}`}
                  className="w-full rounded-sm border border-line"
                  onLoad={() => setScanState("ok")}
                  onError={() => setScanState("missing")}
                />
                <p className="mt-2 text-[11px] leading-relaxed text-faint">
                  Every analytical claim traces to a source document. Scans enter through the
                  Stratus <span className="font-mono">raw-fir</span> bucket → Zia OCR → extraction →
                  human review; this record's structured fields were parsed from this document.
                </p>
              </CardContent>
            </Card>
          )}

          <Guardrail>
            Persons are as recorded in the FIR, pending investigation/trial. Victim/witness identity is
            masked outside the owning jurisdiction; IPC-228A/POCSO identities are masked for all but
            admin/case-officer.
          </Guardrail>
        </div>
      </div>
    </>
  )
}
