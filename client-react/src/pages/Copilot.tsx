import { FileText, SendHorizonal, ShieldCheck } from "lucide-react"
import { useEffect, useReducer, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"

import { PageHeader } from "@/components/common/bits"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { d10 } from "@/lib/format"
import type { Citation, CopilotResponse } from "@/lib/types"
import { cn } from "@/lib/utils"

type Msg =
  | { role: "user"; text: string }
  | { role: "bot"; res: CopilotResponse; pending?: boolean }

/** Module-level thread so the conversation survives route switches. */
let CHAT: Msg[] = [
  {
    role: "bot",
    res: {
      answer:
        "Ask me about incidents, locations, crime types or time windows. I return matching FIRs with citations — and I won't make accusations.",
      citations: [],
    },
  },
]

const EXAMPLES = [
  "chain snatching in BNU",
  "house burglary in Mysuru in May 2024",
  "two-wheeler theft in BNU in March 2025",
  "is the accused guilty?",
]

export function CitationCard({ c, onOpen }: { c: Citation; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full min-w-0 rounded-md border border-border-soft bg-surface-2/50 p-2.5 text-left transition-colors hover:border-primary/40 hover:bg-accent"
    >
      <span className="flex items-center gap-1.5 font-mono text-[11.5px] text-primary">
        <FileText className="size-3" /> {c.fir_no || c.incident_id}
      </span>
      <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[10.5px]">
        <span className="rounded border border-info/30 bg-info-soft px-1 py-px text-info">{c.crime_type}</span>
        <span className="font-mono text-faint">
          {c.district_code} · {d10(c.occurred_at)}
        </span>
      </span>
      {c.snippet && (
        <span className="mt-1 block text-[11px] leading-snug text-muted-foreground">{c.snippet}</span>
      )}
    </button>
  )
}

export default function Copilot() {
  const [, force] = useReducer((x: number) => x + 1, 0)
  const [input, setInput] = useState("")
  const navigate = useNavigate()
  const location = useLocation()
  const threadRef = useRef<HTMLDivElement>(null)
  const askedRef = useRef(false)

  async function ask(q: string) {
    const query = q.trim()
    if (!query) return
    setInput("")
    CHAT.push({ role: "user", text: query })
    const pending: Msg = { role: "bot", res: { answer: "Searching the FIR corpus…", citations: [] }, pending: true }
    CHAT.push(pending)
    force()
    const res = await api.copilot(query)
    CHAT = CHAT.filter((m) => m !== pending)
    CHAT.push({ role: "bot", res })
    force()
  }

  // Ctrl-K palette / other screens hand a question over via router state.
  useEffect(() => {
    const q = (location.state as { ask?: string } | null)?.ask
    if (q && !askedRef.current) {
      askedRef.current = true
      navigate(location.pathname, { replace: true, state: null })
      void ask(q)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight })
  })

  return (
    <>
      <PageHeader
        title="Intelligence Copilot"
        caption="Plain-English questions over the FIR corpus — every answer grounded in cited records. Citations open the case file."
      />

      <Card className="flex h-[calc(100vh-235px)] min-h-[420px] flex-col">
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3 p-4">
          <div ref={threadRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1.5">
            {CHAT.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end gap-2.5">
                  <div className="max-w-[70%] rounded-lg rounded-br-sm bg-primary-deep/60 px-3.5 py-2.5 text-[13px]">
                    {m.text}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex gap-2.5">
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-md border border-amber/30 bg-amber-soft font-mono text-[9.5px] font-bold text-amber">
                    AI
                  </div>
                  <div
                    className={cn(
                      "max-w-[82%] rounded-lg rounded-tl-sm border border-border-soft bg-surface-2/60 px-3.5 py-2.5",
                      m.res.refused && "border-danger/35",
                      m.pending && "animate-pulse",
                    )}
                  >
                    <div className="whitespace-pre-wrap text-[13px] leading-relaxed">{m.res.answer}</div>
                    {m.res.citations.length > 0 && (
                      <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
                        {m.res.citations.slice(0, 6).map((c, j) => (
                          <CitationCard
                            key={j}
                            c={c}
                            onOpen={() => navigate(`/case/${encodeURIComponent(c.incident_id)}`)}
                          />
                        ))}
                      </div>
                    )}
                    {m.res.guardrail && (
                      <div className="mt-2.5 flex items-start gap-1.5 border-t border-border-soft pt-2 text-[10.5px] text-faint">
                        <ShieldCheck className="mt-px size-3 shrink-0 text-ok" />
                        {m.res.guardrail}
                      </div>
                    )}
                  </div>
                </div>
              ),
            )}
          </div>

          <div className="flex flex-wrap gap-1.5">
            {EXAMPLES.map((e) => (
              <button
                key={e}
                onClick={() => void ask(e)}
                className="rounded-full border bg-surface-2/60 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                {e}
              </button>
            ))}
          </div>

          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              void ask(input)
            }}
          >
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="e.g. two-wheeler theft in BNU in March 2025"
              className="bg-surface-2"
              aria-label="Ask the copilot"
            />
            <Button type="submit">
              <SendHorizonal className="size-4" /> Ask
            </Button>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
