import { useState } from "react"

import { EmptyState, Notice, PageHeader, RoleChip, ShimmerRows } from "@/components/common/bits"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { api } from "@/lib/api"
import { useApi } from "@/lib/hooks"
import { presetFor, usePrincipal } from "@/lib/roles"

export default function Audit() {
  const p = usePrincipal()
  const { data, error, loading } = useApi(() => api.audit(150), [p?.role, p?.scope])
  const [filter, setFilter] = useState("")

  if (loading) return <ShimmerRows n={5} h={60} />

  if (error?.status === 403)
    return (
      <Notice title="Audit log restricted">
        The immutable audit trail is visible to <b className="font-mono">SCRB · Admin</b> and{" "}
        <b className="font-mono">Ethics · Oversight</b> only. Current clearance:{" "}
        <b className="font-mono">{presetFor(p)?.label || p?.role}</b> - switch role in the sidebar.
      </Notice>
    )

  const f = filter.trim().toLowerCase()
  const rows = (data?.entries ?? []).filter(
    (e) =>
      !f ||
      [e.actor, e.role, e.action, e.resource, e.query]
        .map((x) => String(x ?? "").toLowerCase())
        .some((x) => x.includes(f)),
  )

  return (
    <>
      <PageHeader
        eyebrow="Govern · Append-only trail"
        title="Audit Log"
        caption="Append-only trail of every privileged read and query - who, what role, which resource, when. The governance backbone."
      >
        <Input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter actor / role / resource…"
          className="h-8 w-[260px] bg-panel-2 font-mono text-[12px]"
          aria-label="Filter audit entries"
        />
      </PageHeader>

      {rows.length === 0 ? (
        <EmptyState>No audit entries{f ? " match the filter" : " yet - interact with governed reads first"}.</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-md border border-line bg-card shadow-panel">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="k-label">Timestamp (IST)</TableHead>
                <TableHead className="k-label">Actor</TableHead>
                <TableHead className="k-label">Role</TableHead>
                <TableHead className="k-label">Action</TableHead>
                <TableHead className="k-label">Resource</TableHead>
                <TableHead className="k-label">Query / route</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((e, i) => (
                <TableRow key={i}>
                  <TableCell className="whitespace-nowrap font-mono text-[11.5px] text-muted-foreground">
                    {String(e.ts ?? "")}
                  </TableCell>
                  <TableCell className="font-mono text-[12px]">{String(e.actor ?? "")}</TableCell>
                  <TableCell><RoleChip role={String(e.role ?? "?")} /></TableCell>
                  <TableCell className="font-mono text-[12px]">{String(e.action ?? "")}</TableCell>
                  <TableCell className="font-mono text-[12px] text-brass">{String(e.resource ?? "")}</TableCell>
                  <TableCell className="max-w-[260px] truncate font-mono text-[11.5px] text-faint">
                    {String(e.query ?? "")}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <p className="text-[11px] text-faint">
        Entries are append-only and persisted to the Audit_Log store (Data Store on Catalyst; CSV
        locally). PII never appears in log lines.
      </p>
    </>
  )
}
