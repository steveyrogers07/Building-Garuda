import type { LucideIcon } from "lucide-react"
import { Car, Landmark, Lock, Phone, ShieldCheck, Timer, User } from "lucide-react"
import type { ReactNode } from "react"

import { Skeleton } from "@/components/ui/skeleton"
import type { CaseDeadline } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Page heading block: eyebrow + display title left, actions right.
 *  Titles set in Saira Condensed — the signage voice of the console. */
export function PageHeader({
  eyebrow,
  title,
  caption,
  children,
}: {
  eyebrow?: ReactNode
  title: ReactNode
  caption?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-line-soft pb-4">
      <div className="min-w-0">
        {eyebrow && <div className="k-label mb-1">{eyebrow}</div>}
        <h2 className="t-display text-[26px] leading-none">{title}</h2>
        {caption && <p className="mt-2 max-w-2xl text-[12.5px] text-muted-foreground">{caption}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  )
}

/** Rubber stamp — the FIR's own vocabulary (case category, gravity,
 *  chargesheet class are literally stamped on the paper original). */
export function Stamp({
  tone = "dim",
  onPaper = false,
  className,
  children,
}: {
  tone?: "brass" | "signal" | "ok" | "warn" | "steel" | "dim"
  onPaper?: boolean
  className?: string
  children: ReactNode
}) {
  const tones: Record<string, string> = {
    brass: "text-brass",
    signal: "text-signal",
    ok: "text-ok",
    warn: "text-warn",
    steel: "text-steel",
    dim: onPaper ? "text-paper-dim" : "text-dim",
  }
  return (
    <span className={cn("stamp", onPaper && "stamp-paper", tones[tone], className)}>
      {children}
    </span>
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
    <div className="relative overflow-hidden rounded-md border border-line bg-panel p-4 shadow-panel">
      <span
        className={cn(
          "absolute inset-y-0 left-0 w-[3px]",
          tone === "accent" ? "bg-brass" : tone === "danger" ? "bg-signal" : "bg-line",
        )}
      />
      <div className="flex items-center justify-between">
        <span className="k-label">{label}</span>
        {Icon && (
          <Icon
            className={cn(
              "size-4",
              tone === "accent" ? "text-brass" : tone === "danger" ? "text-signal" : "text-faint",
            )}
          />
        )}
      </div>
      <div className="t-display tnum mt-2 text-[34px] leading-none">{value}</div>
      {detail && <div className="mt-1.5 text-[11.5px] text-faint">{detail}</div>}
    </div>
  )
}

/** Ethics guardrail strip — every AI/records panel carries one. */
export function Guardrail({ children }: { children: ReactNode }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-sm border border-line-soft bg-panel-2/60 px-3 py-2 text-[11.5px] leading-relaxed text-muted-foreground">
      <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-ok" />
      <span>{children}</span>
    </div>
  )
}

/** PII masking indicator (IPC 228A / POCSO / jurisdiction). */
export function MaskBadge({ reason, onPaper = false }: { reason: string; onPaper?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-[10px]",
        onPaper
          ? "border-paper-line bg-paper-2 text-paper-dim"
          : "border-brass/30 bg-brass-soft text-brass",
      )}
    >
      <Lock className="size-3" />
      {reason}
    </span>
  )
}

const ROLE_TONES: Record<string, string> = {
  suspect: "border-signal/35 bg-signal-soft text-signal",
  accused: "border-signal/35 bg-signal-soft text-signal",
  victim: "border-steel/35 bg-steel-soft text-steel",
  witness: "border-ok/35 bg-ok-soft text-ok",
  complainant: "border-steel/35 bg-steel-soft text-steel",
  vehicle_used: "border-line bg-panel-2 text-muted-foreground",
  phone_used: "border-line bg-panel-2 text-muted-foreground",
}

/** Party-role chip (suspect / victim / witness / …). */
export function RoleChip({ role }: { role: string }) {
  return (
    <span
      className={cn(
        "rounded-sm border px-1.5 py-0.5 font-mono text-[10px] font-medium",
        ROLE_TONES[role] ?? "border-line bg-panel-2 text-muted-foreground",
      )}
    >
      {role}
    </span>
  )
}

const REASON_TONES: Record<string, string> = {
  shared_person: "border-brass/35 bg-brass-soft text-brass",
  shared_vehicle: "border-brass/35 bg-brass-soft text-brass",
  shared_phone: "border-brass/35 bg-brass-soft text-brass",
  mo_cluster: "border-steel/35 bg-steel-soft text-steel",
  series: "border-warn/35 bg-warn-soft text-warn",
  near_repeat: "border-chart-4/35 bg-chart-4/10 text-chart-4",
  semantic: "border-steel/35 bg-steel-soft text-steel",
  same_section: "border-line bg-panel-2 text-muted-foreground",
}

/** Explained-link chip — the "why" on every connection. */
export function ReasonChip({ type, detail }: { type: string; detail: string }) {
  return (
    <span
      className={cn(
        "rounded-sm border px-1.5 py-0.5 font-mono text-[10px]",
        REASON_TONES[type] ?? "border-line bg-panel-2 text-muted-foreground",
      )}
      title={type}
    >
      {detail}
    </span>
  )
}

const DEADLINE_TONES: Record<string, string> = {
  green: "border-ok/30 bg-ok-soft text-ok",
  amber: "border-warn/30 bg-warn-soft text-warn",
  red: "border-signal/40 bg-signal-soft text-signal",
  overdue: "border-signal bg-signal text-white",
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
      <span className="inline-flex items-center gap-1 rounded-sm border border-line bg-panel-2 px-1.5 py-0.5 font-mono text-[10px] text-faint">
        no clock — no arrest yet
      </span>
    ) : null
  }
  const overdue = deadline.days_remaining < 0
  return (
    <span
      title={`Default-bail window: ${deadline.window_days}d from first arrest ${deadline.arrest_date} — chargesheet due ${deadline.due_date} (${deadline.arrested} in custody)`}
      className={cn(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 font-mono text-[10px] font-medium",
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
    <div className={cn("h-[5px] overflow-hidden rounded-full bg-panel-2", className)}>
      <div
        className={cn(
          "h-full rounded-full",
          tone === "amber" ? "bg-brass" : tone === "danger" ? "bg-signal" : "bg-steel",
        )}
        style={{ width: `${w}%` }}
      />
    </div>
  )
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-sm border border-dashed border-line px-4 py-8 text-center text-[12.5px] text-faint">
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
    <div className="flex items-start gap-3 rounded-md border border-line bg-panel p-5 shadow-panel">
      <div
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-sm border",
          kind === "error"
            ? "border-signal/35 bg-signal-soft text-signal"
            : "border-brass/35 bg-brass-soft text-brass",
        )}
      >
        <Lock className="size-4" />
      </div>
      <div className="min-w-0">
        <div className="t-display text-[16px]">{title}</div>
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
        <Skeleton key={i} style={{ height: h }} className="w-full rounded-sm" />
      ))}
    </div>
  )
}
