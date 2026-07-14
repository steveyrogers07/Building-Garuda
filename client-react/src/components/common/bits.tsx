import type { LucideIcon } from "lucide-react"
import { Car, Landmark, Lock, Phone, ShieldCheck, Timer, User } from "lucide-react"
import type { ReactNode } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import type { CaseDeadline } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Page heading block: title + caption left, actions right. */
export function PageHeader({
  title,
  caption,
  children,
}: {
  title: ReactNode
  caption?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-[21px] font-semibold">{title}</h2>
        {caption && <p className="mt-1 max-w-2xl text-[12.5px] text-muted-foreground">{caption}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}

export function KpiCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "default",
}: {
  label: string
  value: ReactNode
  detail?: string
  icon?: LucideIcon
  tone?: "default" | "accent" | "danger"
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-card p-4 shadow-panel",
        tone === "accent" && "border-amber/35",
        tone === "danger" && "border-danger/35",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="k-label">{label}</span>
        {Icon && (
          <Icon
            className={cn(
              "size-4",
              tone === "accent" ? "text-amber" : tone === "danger" ? "text-danger" : "text-faint",
            )}
          />
        )}
      </div>
      <div className="tnum mt-2 font-mono text-[26px] font-bold leading-none">{value}</div>
      {detail && <div className="mt-1.5 text-[11.5px] text-faint">{detail}</div>}
    </div>
  )
}

/** Ethics guardrail strip — every AI/records panel carries one. */
export function Guardrail({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-md border border-border-soft bg-surface-2/60 px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
      <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-ok" />
      <span>{children}</span>
    </div>
  )
}

/** PII masking indicator (IPC 228A / POCSO / jurisdiction). */
export function MaskBadge({ reason }: { reason: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-amber/30 bg-amber-soft px-1.5 py-0.5 font-mono text-[10px] text-amber">
      <Lock className="size-3" />
      {reason}
    </span>
  )
}

const ROLE_TONES: Record<string, string> = {
  suspect: "border-danger/30 bg-danger-soft text-danger",
  accused: "border-danger/30 bg-danger-soft text-danger",
  victim: "border-info/30 bg-info-soft text-info",
  witness: "border-ok/30 bg-ok-soft text-ok",
  complainant: "border-info/30 bg-info-soft text-info",
  vehicle_used: "border-border bg-surface-2 text-muted-foreground",
  phone_used: "border-border bg-surface-2 text-muted-foreground",
}

/** Party-role chip (suspect / victim / witness / …). */
export function RoleChip({ role }: { role: string }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium",
        ROLE_TONES[role] ?? "border-border bg-surface-2 text-muted-foreground",
      )}
    >
      {role}
    </span>
  )
}

const REASON_TONES: Record<string, string> = {
  shared_person: "border-amber/30 bg-amber-soft text-amber",
  shared_vehicle: "border-amber/30 bg-amber-soft text-amber",
  shared_phone: "border-amber/30 bg-amber-soft text-amber",
  mo_cluster: "border-info/30 bg-info-soft text-info",
  series: "border-warn/30 bg-warn-soft text-warn",
  near_repeat: "border-chart-4/30 bg-chart-4/10 text-chart-4",
  semantic: "border-info/30 bg-info-soft text-info",
  same_section: "border-border bg-surface-2 text-muted-foreground",
}

/** Explained-link chip — the "why" on every connection. */
export function ReasonChip({ type, detail }: { type: string; detail: string }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-0.5 font-mono text-[10px]",
        REASON_TONES[type] ?? "border-border bg-surface-2 text-muted-foreground",
      )}
      title={type}
    >
      {detail}
    </span>
  )
}

const DEADLINE_TONES: Record<string, string> = {
  green: "border-ok/30 bg-ok-soft text-ok",
  amber: "border-amber/30 bg-amber-soft text-amber",
  red: "border-danger/40 bg-danger-soft text-danger",
  overdue: "border-danger bg-danger text-white",
}

/** §1 default-bail clock chip — chargesheet due 60d (90d Heinous) from first
 *  arrest (CrPC 167(2)/BNSS 187). `verbose` renders a muted chip when no clock
 *  runs (nobody arrested yet) instead of nothing. */
export function DeadlineBadge({
  deadline,
  verbose = false,
}: {
  deadline?: CaseDeadline | null
  verbose?: boolean
}) {
  if (!deadline) {
    return verbose ? (
      <span className="inline-flex items-center gap-1 rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
        no clock — no arrest yet
      </span>
    ) : null
  }
  const overdue = deadline.days_remaining < 0
  return (
    <span
      title={`Default-bail window: ${deadline.window_days}d from first arrest ${deadline.arrest_date} — chargesheet due ${deadline.due_date} (${deadline.arrested} in custody)`}
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[10px] font-medium",
        DEADLINE_TONES[deadline.bucket],
      )}
    >
      <Timer className="size-3" />
      {overdue
        ? `CS overdue ${-deadline.days_remaining}d`
        : `CS due ${deadline.days_remaining}d`}
    </span>
  )
}

export function entityIcon(type?: string): LucideIcon {
  if (type === "vehicle") return Car
  if (type === "phone") return Phone
  if (type === "place") return Landmark
  return User
}

/** Horizontal magnitude bar for tables/lists. */
export function MiniBar({
  value,
  max,
  tone = "primary",
  className,
}: {
  value: number
  max: number
  tone?: "primary" | "amber" | "danger"
  className?: string
}) {
  const w = Math.max(2, Math.min(100, (100 * value) / (max || 1)))
  return (
    <div className={cn("h-1.5 overflow-hidden rounded-full bg-surface-2", className)}>
      <div
        className={cn(
          "h-full rounded-full",
          tone === "amber" ? "bg-amber" : tone === "danger" ? "bg-danger" : "bg-primary",
        )}
        style={{ width: `${w}%` }}
      />
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-border-soft px-4 py-8 text-center text-[12.5px] text-faint">
      {children}
    </div>
  )
}

/** Access / error notice (403 clearance, 404, offline). */
export function Notice({
  kind = "lock",
  title,
  children,
  action,
}: {
  kind?: "lock" | "error"
  title: string
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border bg-card p-5 shadow-panel">
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-md border",
          kind === "error"
            ? "border-danger/30 bg-danger-soft text-danger"
            : "border-amber/30 bg-amber-soft text-amber",
        )}
      >
        <Lock className="size-4" />
      </div>
      <div className="min-w-0">
        <div className="font-mono text-[13.5px] font-semibold">{title}</div>
        <div className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground">{children}</div>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  )
}

export function ShimmerRows({ n = 3, h = 52 }: { n?: number; h?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} style={{ height: h }} className="w-full" />
      ))}
    </div>
  )
}
