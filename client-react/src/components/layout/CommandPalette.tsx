import { FileText, Landmark, MessageSquareText, SearchIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"

import { entityIcon } from "@/components/common/bits"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command"
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog"
import { api } from "@/lib/api"
import { d10, fmt } from "@/lib/format"
import type { SearchResult } from "@/lib/types"

/** Ctrl-K universal search — cases, people, vehicles, phones, places and
 *  semantic narrative matches, all deep-linked. Results are server-filtered
 *  (structured + semantic), so cmdk's own filtering is disabled. */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const navigate = useNavigate()
  const [q, setQ] = useState("")
  const [res, setRes] = useState<SearchResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) {
      setQ("")
      setRes(null)
      return
    }
  }, [open])

  useEffect(() => {
    const query = q.trim()
    if (query.length < 2) {
      setRes(null)
      return
    }
    setBusy(true)
    const t = setTimeout(() => {
      api
        .search(query)
        .then((r) => setRes(r))
        .catch(() => setRes({ groups: {}, note: "Search unavailable for this role." }))
        .finally(() => setBusy(false))
    }, 220)
    return () => clearTimeout(t)
  }, [q])

  function go(path: string) {
    onOpenChange(false)
    navigate(path)
  }

  const g = res?.groups ?? {}
  const hasHits =
    (g.cases?.length || 0) +
      (g.people?.length || 0) +
      (g.vehicles?.length || 0) +
      (g.phones?.length || 0) +
      (g.places?.length || 0) +
      (res?.semantic?.length || 0) >
    0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[18%] translate-y-0 overflow-hidden p-0 sm:max-w-xl" showCloseButton={false}>
        <DialogTitle className="sr-only">Universal search</DialogTitle>
        <DialogDescription className="sr-only">
          Search cases, people, vehicles, phones and places
        </DialogDescription>
        <Command shouldFilter={false} className="**:data-[slot=command-input-wrapper]:h-12">
          <CommandInput
            placeholder="Search cases, people, vehicles, phones, places…"
            value={q}
            onValueChange={setQ}
          />
          <CommandList className="max-h-[420px]">
            {q.trim().length < 2 ? (
              <div className="px-4 py-8 text-center text-[12.5px] text-faint">
                Type at least 2 characters — try <span className="font-mono text-brass">KA68MC3164</span>{" "}
                or <span className="font-mono">Aayush</span>
              </div>
            ) : (
              <>
                {!hasHits && !busy && (
                  <CommandEmpty>{res?.note || "No matches in the canonical store."}</CommandEmpty>
                )}
                {!!g.cases?.length && (
                  <CommandGroup heading="Cases">
                    {g.cases.map((c) => (
                      <CommandItem
                        key={c.incident_id}
                        value={`case-${c.incident_id}`}
                        onSelect={() => go(`/case/${encodeURIComponent(c.incident_id)}`)}
                      >
                        <FileText className="text-faint" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-mono text-[12.5px]">{c.fir_no || c.incident_id}</div>
                          <div className="truncate text-[11px] text-faint">
                            {c.crime_type} · {c.district_code} · {d10(c.occurred_at)}
                          </div>
                        </div>
                        <span className="text-[10px] text-faint">{c.status}</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {(["people", "vehicles", "phones"] as const).map((k) =>
                  g[k]?.length ? (
                    <CommandGroup key={k} heading={k[0].toUpperCase() + k.slice(1)}>
                      {g[k]!.map((p) => {
                        const Icon = entityIcon(p.type)
                        return (
                          <CommandItem
                            key={p.canonical_id}
                            value={`${k}-${p.canonical_id}`}
                            onSelect={() => go(`/entity/${encodeURIComponent(p.canonical_id)}`)}
                          >
                            <Icon className="text-faint" />
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[12.5px]">
                                {p.value}
                                {p.masked && (
                                  <span className="ml-1.5 font-mono text-[10px] text-brass">
                                    [masked: {p.masked}]
                                  </span>
                                )}
                              </div>
                              <div className="truncate text-[11px] text-faint">
                                {fmt(p.incidents)} incidents · {(p.districts || []).join(" ")}
                              </div>
                            </div>
                            <span className="font-mono text-[10px] text-faint">{p.type}</span>
                          </CommandItem>
                        )
                      })}
                    </CommandGroup>
                  ) : null,
                )}
                {!!g.places?.length && (
                  <CommandGroup heading="Places">
                    {g.places.map((p) => (
                      <CommandItem key={p.code} value={`place-${p.code}`} onSelect={() => go("/map")}>
                        <Landmark className="text-faint" />
                        <span className="font-mono text-[12.5px]">{p.code}</span>
                        <span className="ml-auto text-[11px] text-faint">{fmt(p.incidents)} incidents</span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                {!!res?.semantic?.length && (
                  <CommandGroup heading="Narrative matches (semantic)">
                    {res.semantic.map((c) => (
                      <CommandItem
                        key={`sem-${c.incident_id}`}
                        value={`sem-${c.incident_id}`}
                        onSelect={() => go(`/case/${encodeURIComponent(c.incident_id)}`)}
                      >
                        <SearchIcon className="text-faint" />
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-mono text-[12.5px]">{c.fir_no || c.incident_id}</div>
                          <div className="truncate text-[11px] text-faint">{(c.snippet || "").slice(0, 80)}…</div>
                        </div>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                )}
                <CommandSeparator />
                <CommandGroup heading="Assistant">
                  <CommandItem
                    value={`ask-${q}`}
                    onSelect={() => {
                      onOpenChange(false)
                      navigate("/copilot", { state: { ask: q.trim() } })
                    }}
                  >
                    <MessageSquareText className="text-brass" />
                    <span className="text-[12.5px]">
                      Ask copilot: <span className="text-muted-foreground">“{q.trim()}”</span>
                    </span>
                  </CommandItem>
                </CommandGroup>
              </>
            )}
          </CommandList>
          <div className="flex items-center gap-3 border-t px-3 py-1.5 font-mono text-[10px] text-faint">
            {res?.took_ms != null && <span>{res.took_ms}ms</span>}
            <span>↑↓ navigate · Enter open · Esc close</span>
            <span className="ml-auto">searches are audited</span>
          </div>
        </Command>
      </DialogContent>
    </Dialog>
  )
}
