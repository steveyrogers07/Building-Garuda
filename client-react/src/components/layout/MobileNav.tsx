import {
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquareText,
  UserX,
} from "lucide-react"
import { useState } from "react"
import { NavLink, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { NAV } from "@/components/layout/Sidebar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { presetFor, ROLE_PRESETS, setPrincipal, usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"

/** The four surfaces a field officer actually reaches for on a phone. */
const TABS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/my-cases", label: "My Cases", icon: ClipboardList },
  { to: "/absconding", label: "Absconding", icon: UserX },
  { to: "/copilot", label: "Copilot", icon: MessageSquareText },
]

/** Bottom tab bar (< lg) — the desktop sidebar's mobile counterpart. The full
 *  nav, the clearance/role switcher and sign-out live in the "More" sheet. */
export function MobileNav() {
  const principal = usePrincipal()
  const navigate = useNavigate()
  const preset = presetFor(principal)
  const [moreOpen, setMoreOpen] = useState(false)

  function switchRole(id: string) {
    const r = ROLE_PRESETS.find((x) => x.id === id)
    if (!r || !principal) return
    setPrincipal({ ...principal, role: r.role, scope: r.scope })
    toast(`Clearance switched — ${r.label}`, {
      description: "Jurisdiction gates and PII masking now apply server-side.",
    })
  }

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-console-deep pb-[env(safe-area-inset-bottom)] lg:hidden"
      aria-label="Primary"
    >
      <div className="grid grid-cols-5">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 border-t-2 border-transparent py-2 text-[10px] text-muted-foreground",
                isActive && "border-brass bg-panel font-medium text-foreground",
              )
            }
          >
            {({ isActive }) => (
              <>
                <t.icon className={cn("size-4.5", isActive ? "text-brass" : "text-faint")} />
                {t.label}
              </>
            )}
          </NavLink>
        ))}

        <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
          <SheetTrigger asChild>
            <button
              className="flex flex-col items-center gap-0.5 border-t-2 border-transparent py-2 text-[10px] text-muted-foreground"
              aria-label="More navigation"
            >
              <Menu className="size-4.5 text-faint" />
              More
            </button>
          </SheetTrigger>
          <SheetContent side="bottom" className="max-h-[80vh] overflow-y-auto border-line bg-console-deep">
            <SheetTitle className="k-label text-left">GARUDA Console</SheetTitle>

            <div className="mt-2 grid grid-cols-2 gap-1">
              {NAV.flatMap((g) => g.items).map((it) => (
                <NavLink
                  key={it.to}
                  to={it.to}
                  end={it.end}
                  onClick={() => setMoreOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-sm border border-transparent px-3 py-2.5 text-[13px] text-muted-foreground",
                      isActive && "border-line bg-panel font-medium text-foreground",
                    )
                  }
                >
                  <it.icon className="size-4 text-faint" />
                  {it.label}
                </NavLink>
              ))}
            </div>

            <div className="mt-4 border-t border-line pt-3">
              <div className="k-label mb-1.5">Clearance / Role</div>
              <Select value={preset?.id} onValueChange={switchRole}>
                <SelectTrigger className="w-full bg-panel" size="sm" aria-label="Switch clearance role">
                  <SelectValue
                    placeholder={`${principal?.role}${principal?.scope ? ":" + principal.scope : ""}`}
                  />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_PRESETS.map((r) => (
                    <SelectItem key={r.id} value={r.id} textValue={r.label}>
                      <span className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className="w-8 justify-center border-brass/40 px-1 font-mono text-[9px] text-brass"
                        >
                          {r.clearance}
                        </Badge>
                        {r.label}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                variant="ghost"
                className="mt-3 w-full justify-start gap-2 text-faint hover:text-signal"
                onClick={() => {
                  setPrincipal(null)
                  navigate("/login")
                }}
              >
                <LogOut className="size-4" /> Sign out
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </nav>
  )
}
