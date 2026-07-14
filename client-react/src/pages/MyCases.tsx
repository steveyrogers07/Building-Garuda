import { AlarmClockOff, Flame, FolderOpen, Timer } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import {
  DeadlineBadge,
  EmptyState,
  KpiCard,
  Notice,
  PageHeader,
  ShimmerRows,
  Stamp,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { fmt } from "@/lib/format"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"
import type { OfficerWorklist } from "@/lib/types"
import { cn } from "@/lib/utils"

/** §2 — the IO's landing view: open cases worst-first by the §1 default-bail
 *  clock (CrPC 167(2)/BNSS 187: chargesheet within 60d of arrest, 90d for
 *  Heinous, or the accused walks), then case age, then gravity. In production
 *  this binds to the signed-in officer's KGID; the demo console picks any
 *  officer in jurisdiction. Selection is district-first, then the officer
 *  within it — both always drawn from the roster, so a scoped role never fires
 *  an out-of-jurisdiction fetch (no 403 flash). */
export default function MyCases() {
  const p = usePrincipal()
  const navigate = useNavigate()
  const scoped = p?.role === "district" || p?.role === "station"
  const roster = useApi(() => api.officers(), [p?.role, p?.scope])
  const geo = useApi(() => api.geoDistricts(), [])
  const officers = roster.data?.officers ?? []
  const [district, setDistrict] = useState("")
  const [oid, setOid] = useState("")

  const nameOf = useMemo(() => {
    const m = new Map((geo.data?.districts ?? []).map((d) => [d.code, d.name || d.code]))
    return (code: string) => m.get(code) || code
  }, [geo.data])

  // districts present in the roster, each with its officer count + urgent load
  const districts = useMemo(() => {
    const m = new Map<string, { officers: number; urgent: number }>()
    for (const o of officers) {
      const e = m.get(o.district_code ?? "") ?? { officers: 0, urgent: 0 }
      e.officers += 1
      e.urgent += o.urgent
      m.set(o.district_code ?? "", e)
    }
    return [...m.entries()]
      .filter(([code]) => code)
      .sort(([a], [b]) => a.localeCompare(b))
  }, [officers])

  const officersInDistrict = useMemo(
    () => officers.filter((o) => o.district_code === district),
    [officers, district],
  )

  // default the district once the roster lands (their own, for scoped roles)
  useEffect(() => {
    if (districts.length && !districts.some(([c]) => c === district)) {
      setDistrict(districts[0][0])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [districts])

  // default the officer within the chosen district (worst worklist first)
  useEffect(() => {
    if (officersInDistrict.length && !officersInDistrict.some((o) => o.officer_id === oid)) {
      setOid(officersInDistrict[0].officer_id)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [officersInDistrict])

  // switch district + its first officer together, so the worklist never shows
  // one district's header over another's officer for a frame
  function pickDistrict(code: string) {
    setDistrict(code)
    setOid(officers.find((o) => o.district_code === code)?.officer_id ?? "")
  }

  const wl = useApi<OfficerWorklist | null>(
    () => (oid ? api.officerCases(oid) : Promise.resolve(null)),
    [oid, p?.role, p?.scope],
  )
  const w = wl.data ?? undefined
  const s = w?.summary

  return (
    <>
      <PageHeader
        eyebrow="Field operations · CrPC 167(2) / BNSS 187"
        title="My Cases"
        caption="Open cases worst-first on the default-bail clock — chargesheet due 60 days from first arrest (90 for Heinous) or the accused walks on default bail."
      >
        {!scoped && (
          <Select value={district} onValueChange={pickDistrict}>
            <SelectTrigger className="w-[230px] bg-panel-2" aria-label="Select district">
              <SelectValue placeholder="Select district…" />
            </SelectTrigger>
            <SelectContent>
              {districts.map(([code, e]) => (
                <SelectItem key={code} value={code} textValue={`${nameOf(code)} ${code}`}>
                  <span className="flex w-full items-center gap-2">
                    <span className="truncate">{nameOf(code)}</span>
                    <span className="font-mono text-[10px] text-faint">{code}</span>
                    {e.urgent > 0 && (
                      <Badge
                        variant="outline"
                        className="ml-auto border-signal/40 bg-signal-soft px-1 font-mono text-[9px] text-signal"
                      >
                        {e.urgent}
                      </Badge>
                    )}
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Select value={oid} onValueChange={setOid} disabled={!officersInDistrict.length}>
          <SelectTrigger className="w-[260px] bg-panel-2" aria-label="Select officer">
            <SelectValue placeholder="Select officer…" />
          </SelectTrigger>
          <SelectContent>
            {officersInDistrict.map((o) => (
              <SelectItem key={o.officer_id} value={o.officer_id} textValue={o.name || o.officer_id}>
                <span className="flex w-full items-center gap-2">
                  <span className="truncate">{o.name || o.officer_id}</span>
                  <span className="font-mono text-[10px] text-faint">
                    {o.rank} · {o.unit_code}
                  </span>
                  {o.urgent > 0 && (
                    <Badge
                      variant="outline"
                      className="ml-auto border-signal/40 bg-signal-soft px-1 font-mono text-[9px] text-signal"
                    >
                      {o.urgent} urgent
                    </Badge>
                  )}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PageHeader>

      {roster.error?.status === 403 ? (
        <Notice title="Access restricted">
          {roster.error.detail || "Case worklists are not available to this role."} Current
          clearance: <b className="font-mono">{presetFor(p)?.label || p?.role}</b>.
        </Notice>
      ) : !roster.loading && officers.length === 0 ? (
        <EmptyState>
          No officers on record for this jurisdiction in the current dataset — switch clearance
          in the sidebar to view another desk.
        </EmptyState>
      ) : wl.error?.status === 403 ? (
        <Notice title="Access restricted">
          {wl.error.detail || "This officer is outside your jurisdiction."} Current clearance:{" "}
          <b className="font-mono">{presetFor(p)?.label || p?.role}</b>.
        </Notice>
      ) : !w ? (
        <ShimmerRows n={4} h={90} />
      ) : (
        <div
          className={cn(
            "space-y-5 transition-opacity duration-200",
            wl.loading && "pointer-events-none opacity-60",
          )}
        >
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <KpiCard
              label="Open cases"
              value={fmt(s?.open)}
              detail={`${w.officer.name || oid} · ${w.officer.rank || ""} · ${w.officer.district_code || ""}/${w.officer.unit_code || ""}`}
              icon={FolderOpen}
            />
            <KpiCard
              label="Default bail passed"
              value={fmt(s?.overdue)}
              detail="chargesheet window already blown"
              icon={AlarmClockOff}
              tone={(s?.overdue ?? 0) > 0 ? "danger" : "default"}
            />
            <KpiCard
              label="Filing due < 10d"
              value={fmt(s?.red)}
              detail={`${fmt(s?.amber)} more inside 30d · ${fmt(s?.green)} comfortable`}
              icon={Timer}
              tone={(s?.red ?? 0) > 0 ? "danger" : "default"}
            />
            <KpiCard
              label="Heinous on desk"
              value={fmt(s?.heinous)}
              detail={`${fmt(s?.no_clock)} open with nobody arrested yet`}
              icon={Flame}
              tone="accent"
            />
          </div>

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <div className="k-label">Worklist · statutory urgency → case age → gravity</div>
                <CardTitle className="t-display mt-1 text-[17px]">Open cases on this desk</CardTitle>
              </div>
              <Badge variant="outline" className="font-mono text-[10px] text-faint">
                as of {w.as_of} · dataset day
              </Badge>
            </CardHeader>
            <CardContent>
              {w.cases.length ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="k-label">Deadline</TableHead>
                      <TableHead className="k-label">FIR</TableHead>
                      <TableHead className="k-label">Crime</TableHead>
                      <TableHead className="k-label">Gravity</TableHead>
                      <TableHead className="k-label">Jurisdiction</TableHead>
                      <TableHead className="k-label text-right">Case age</TableHead>
                      <TableHead className="k-label">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {w.cases.map((c) => (
                      <TableRow
                        key={c.incident_id}
                        className="cursor-pointer"
                        onClick={() => navigate(`/case/${encodeURIComponent(c.incident_id)}`)}
                      >
                        <TableCell>
                          <DeadlineBadge deadline={c.deadline} verbose />
                        </TableCell>
                        <TableCell className="font-mono text-[12px] text-primary">
                          {c.fir_no || c.incident_id}
                        </TableCell>
                        <TableCell className="text-[12.5px]">{c.crime_type}</TableCell>
                        <TableCell>
                          {c.gravity === "Heinous" ? (
                            <Stamp tone="signal">Heinous</Stamp>
                          ) : (
                            <span className="text-[11px] text-faint">{c.gravity || "—"}</span>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-[11.5px] text-muted-foreground">
                          {c.district_code} / {c.station_code}
                        </TableCell>
                        <TableCell className="tnum text-right font-mono text-[12px]">
                          {c.case_age_days == null ? "–" : `${fmt(c.case_age_days)}d`}
                        </TableCell>
                        <TableCell className="text-[11.5px] text-muted-foreground">{c.status}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <EmptyState>No open cases on this desk — clean slate.</EmptyState>
              )}
              <p className="mt-3.5 text-[11px] leading-relaxed text-faint">
                Clock = CrPC 167(2)/BNSS 187 default-bail window from the first arrest on the case
                (60d Non-Heinous / 90d Heinous). “No clock” = investigation open with nobody in
                custody, so no filing deadline runs yet. All day-math anchors to the dataset’s
                latest recorded day ({w.as_of}), not wall-clock time.
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}
