import {
  Building2,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Map as MapIcon,
  MessageSquareText,
  ScrollText,
  Search,
  Siren,
  UserX,
  Waypoints,
} from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { KspWordmark } from "@/components/brand/KspCrest"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { initials, presetFor, ROLE_PRESETS, setPrincipal, usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"

const NAV = [
  {
    group: "Command",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
      { to: "/my-cases", label: "My Cases", icon: ClipboardList },
      { to: "/district", label: "District Command", icon: Building2 },
      { to: "/alerts", label: "Alerts & Risk", icon: Siren },
    ],
  },
  {
    group: "Investigate",
    items: [
      { to: "/absconding", label: "Absconding Board", icon: UserX },
      { to: "/network", label: "Network Reveal", icon: Waypoints },
      { to: "/map", label: "Hotspot Map", icon: MapIcon },
      { to: "/search", label: "Universal Search", icon: Search },
    ],
  },
  {
    group: "Assist",
    items: [{ to: "/copilot", label: "Copilot", icon: MessageSquareText }],
  },
  {
    group: "Govern",
    items: [{ to: "/audit", label: "Audit Log", icon: ScrollText }],
  },
]

export function Sidebar() {
  const principal = usePrincipal()
  const navigate = useNavigate()
  const preset = presetFor(principal)

  function switchRole(id: string) {
    const r = ROLE_PRESETS.find((x) => x.id === id)
    if (!r || !principal) return
    setPrincipal({ ...principal, role: r.role, scope: r.scope })
    toast(`Clearance switched — ${r.label}`, {
      description: "Jurisdiction gates and PII masking now apply server-side.",
    })
  }

  return (
    <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col border-r bg-surface">
      <div className="border-b px-4 py-4">
        <KspWordmark />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV.map((g) => (
          <div key={g.group} className="mb-5">
            <div className="k-label mb-1.5 px-3">{g.group}</div>
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.end}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                    isActive && "bg-accent font-medium text-foreground",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <it.icon className={cn("size-4", isActive ? "text-primary" : "text-faint")} />
                    {it.label}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t px-3 py-3">
        <div className="k-label mb-1.5 px-1">Clearance / Role</div>
        <Select value={preset?.id} onValueChange={switchRole}>
          <SelectTrigger className="w-full bg-surface-2" size="sm" aria-label="Switch clearance role">
            <SelectValue placeholder={`${principal?.role}${principal?.scope ? ":" + principal.scope : ""}`} />
          </SelectTrigger>
          <SelectContent>
            {ROLE_PRESETS.map((r) => (
              <SelectItem key={r.id} value={r.id} textValue={r.label}>
                <span className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className="w-8 justify-center border-primary/40 px-1 font-mono text-[9px] text-primary"
                  >
                    {r.clearance}
                  </Badge>
                  {r.label}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="mt-1.5 px-1 text-[10.5px] leading-snug text-faint">
          {preset?.desc || "Custom principal — masking enforced server-side."}
        </p>

        <div className="mt-3 flex items-center gap-2.5 border-t pt-3">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary-deep font-mono text-[11px] font-bold text-white">
            {initials(principal)}
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[12.5px] font-medium">{principal?.name || principal?.actor}</div>
            <div className="truncate font-mono text-[10px] text-faint">{preset?.label || principal?.role}</div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-faint hover:text-danger"
            aria-label="Sign out"
            onClick={() => {
              setPrincipal(null)
              navigate("/login")
            }}
          >
            <LogOut className="size-3.5" />
          </Button>
        </div>
      </div>
    </aside>
  )
}
