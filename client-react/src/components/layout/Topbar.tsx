import { Search } from "lucide-react"
import { useEffect, useState } from "react"
import { useLocation } from "react-router-dom"

import { subscribeDataMode, type DataMode } from "@/lib/api"
import { istNow } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const CRUMBS: Record<string, string> = {
  "/": "Operations Overview",
  "/my-cases": "My Cases",
  "/district": "District Command",
  "/alerts": "Alerts & Risk",
  "/absconding": "Absconding Board",
  "/network": "Network Reveal",
  "/map": "Hotspot Map",
  "/search": "Universal Search",
  "/copilot": "Intelligence Copilot",
  "/audit": "Audit Log",
}

function crumbFor(path: string): string {
  if (CRUMBS[path]) return CRUMBS[path]
  const m = path.match(/^\/(case|entity)\/(.+)$/)
  if (m) return (m[1] === "case" ? "Case · " : "Entity · ") + decodeURIComponent(m[2])
  return "GARUDA"
}

function useDataMode(): DataMode {
  const [m, setM] = useState<DataMode>("live")
  useEffect(() => subscribeDataMode(setM), [])
  return m
}

function Clock() {
  const [t, setT] = useState(istNow())
  useEffect(() => {
    const id = setInterval(() => setT(istNow()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="tnum font-mono text-[11.5px] text-muted-foreground">
      <b className="font-semibold text-foreground">{t}</b> IST
    </span>
  )
}

export function Topbar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const loc = useLocation()
  const mode = useDataMode()

  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-line bg-console/85 px-3 backdrop-blur lg:h-[52px] lg:gap-4 lg:px-5">
      <div className="min-w-0 flex-1 truncate font-mono text-[12px] text-muted-foreground lg:flex-none">
        <span className="text-faint">/ </span>
        <span className="text-foreground">{crumbFor(loc.pathname)}</span>
      </div>

      <button
        onClick={onOpenPalette}
        className="flex h-8 w-8 shrink-0 items-center justify-center gap-2 rounded-sm border border-line bg-panel text-[12px] text-faint transition-colors hover:border-brass/40 hover:text-muted-foreground lg:ml-auto lg:w-[330px] lg:justify-start lg:px-3"
        aria-label="Open universal search"
      >
        <Search className="size-3.5" />
        <span className="hidden flex-1 text-left lg:block">Search cases, people, vehicles…</span>
        <kbd className="hidden rounded-sm border border-line bg-console px-1.5 font-mono text-[10px] lg:inline">Ctrl K</kbd>
      </button>

      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider",
              mode === "live"
                ? "border-ok/35 bg-ok-soft text-ok"
                : "border-brass/40 bg-brass-soft text-brass",
            )}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                mode === "live" ? "bg-ok" : "animate-pulse bg-brass",
              )}
            />
            {mode === "live" ? "Live" : "Mock data"}
          </span>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          {mode === "live"
            ? "Connected to the analytics brain (same-origin API)."
            : "Brain unreachable - rendering planted demo fixtures."}
        </TooltipContent>
      </Tooltip>

      <span className="hidden sm:inline">
        <Clock />
      </span>
    </header>
  )
}
