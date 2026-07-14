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
    <header className="sticky top-0 z-30 flex h-[52px] items-center gap-4 border-b border-line bg-console/85 px-5 backdrop-blur">
      <div className="min-w-0 font-mono text-[12px] text-muted-foreground">
        <span className="text-faint">/ </span>
        <span className="text-foreground">{crumbFor(loc.pathname)}</span>
      </div>

      <button
        onClick={onOpenPalette}
        className="ml-auto flex h-8 w-[330px] items-center gap-2 rounded-sm border border-line bg-panel px-3 text-[12px] text-faint transition-colors hover:border-brass/40 hover:text-muted-foreground"
        aria-label="Open universal search"
      >
        <Search className="size-3.5" />
        <span className="flex-1 text-left">Search cases, people, vehicles…</span>
        <kbd className="rounded-sm border border-line bg-console px-1.5 font-mono text-[10px]">Ctrl K</kbd>
      </button>

      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider",
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
            : "Brain unreachable — rendering planted demo fixtures."}
        </TooltipContent>
      </Tooltip>

      <Clock />
    </header>
  )
}
