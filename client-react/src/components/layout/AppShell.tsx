import { FileText, X } from "lucide-react"
import { useEffect, useState } from "react"
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom"

import { ClassificationBar } from "@/components/brand/ClassificationBar"
import { entityIcon } from "@/components/common/bits"
import { CommandPalette } from "@/components/layout/CommandPalette"
import { Sidebar } from "@/components/layout/Sidebar"
import { Topbar } from "@/components/layout/Topbar"
import { TooltipProvider } from "@/components/ui/tooltip"
import { usePrincipal } from "@/lib/roles"
import { cn } from "@/lib/utils"
import { closeTab, tabRoute, useWorkTabs, type WorkTab } from "@/lib/workspace"

/** Open case/entity objects — styled as manila folder tabs on the desk edge:
 *  the documents currently pulled out of the register. */
function TabStrip() {
  const tabs = useWorkTabs()
  const navigate = useNavigate()
  const loc = useLocation()
  if (!tabs.length) return null

  function TabChip({ t }: { t: WorkTab }) {
    const active = loc.pathname === tabRoute(t)
    const Icon = t.type === "case" ? FileText : entityIcon(t.icon)
    return (
      <button
        onClick={() => navigate(tabRoute(t))}
        className={cn(
          "group flex h-7 shrink-0 items-center gap-1.5 rounded-t-md border border-b-0 px-2.5 font-mono text-[11px] transition-colors",
          active
            ? "border-paper-line bg-paper text-paper-ink"
            : "border-line bg-panel text-muted-foreground hover:text-foreground",
        )}
      >
        <Icon className={cn("size-3", active ? "text-paper-dim" : "text-faint")} />
        <span className="max-w-[160px] truncate">{t.title || t.id}</span>
        <span
          role="button"
          aria-label={`Close ${t.title || t.id}`}
          className={cn(
            "rounded-sm p-0.5 opacity-60 group-hover:opacity-100",
            active ? "text-paper-dim hover:text-signal" : "text-faint hover:text-signal",
          )}
          onClick={(e) => {
            e.stopPropagation()
            const next = closeTab(t.type, t.id)
            if (active) navigate(next ? tabRoute(next) : "/")
          }}
        >
          <X className="size-3" />
        </span>
      </button>
    )
  }

  return (
    <div className="flex items-end gap-1.5 overflow-x-auto border-b border-line bg-console-deep px-4 pt-1.5">
      <span className="k-label mb-1.5 mr-1 shrink-0">Workspace</span>
      {tabs.map((t) => (
        <TabChip key={t.type + t.id} t={t} />
      ))}
    </div>
  )
}

export function AppShell() {
  const principal = usePrincipal()
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  if (!principal) return <Navigate to="/login" replace />

  return (
    <TooltipProvider delayDuration={250}>
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <ClassificationBar />
          <Topbar onOpenPalette={() => setPaletteOpen(true)} />
          <TabStrip />
          <main className="mx-auto w-full max-w-[1500px] flex-1 space-y-5 px-6 py-6">
            <Outlet />
          </main>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </TooltipProvider>
  )
}
