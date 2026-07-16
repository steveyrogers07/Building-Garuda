import { FileText, Languages, Mic, MicOff, SendHorizonal, ShieldCheck } from "lucide-react"
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

/** Browser speech recognition (Chrome ships kn-IN natively — no credits, no
 *  cloud keys; Catalyst Zia has no STT, so this IS the §4.13 voice front). */
type Recognition = {
  lang: string
  interimResults: boolean
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onend: (() => void) | null
  onerror: (() => void) | null
  start: () => void
  stop: () => void
}

function makeRecognition(): Recognition | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => Recognition
    webkitSpeechRecognition?: new () => Recognition
  }
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition
  return Ctor ? new Ctor() : null
}

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
  "ತುಮಕೂರು ಜಿಲ್ಲೆಯಲ್ಲಿ ಸರಗಳ್ಳತನ ಎಷ್ಟು",
  "is the accused guilty?",
]

export function CitationCard({ c, onOpen }: { c: Citation; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full min-w-0 rounded-md border border-line-soft bg-panel-2/50 p-2.5 text-left transition-colors hover:border-brass/40 hover:bg-accent"
    >
      <span className="flex items-center gap-1.5 font-mono text-[11.5px] text-brass">
        <FileText className="size-3" /> {c.fir_no || c.incident_id}
      </span>
      <span className="mt-1 flex flex-wrap items-center gap-1.5 text-[10.5px]">
        <span className="rounded border border-steel/30 bg-steel-soft px-1 py-px text-steel">{c.crime_type}</span>
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
  const [listening, setListening] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const threadRef = useRef<HTMLDivElement>(null)
  const askedRef = useRef(false)
  const recRef = useRef<Recognition | null>(null)
  const micSupported = useRef<boolean | null>(null)
  if (micSupported.current === null) micSupported.current = makeRecognition() !== null

  async function ask(q: string, lang?: string) {
    const query = q.trim()
    if (!query) return
    setInput("")
    CHAT.push({ role: "user", text: query })
    const pending: Msg = { role: "bot", res: { answer: "Searching the FIR corpus…", citations: [] }, pending: true }
    CHAT.push(pending)
    force()
    const res = await api.copilot(query, lang)
    CHAT = CHAT.filter((m) => m !== pending)
    CHAT.push({ role: "bot", res })
    force()
  }

  function toggleMic() {
    if (listening) {
      recRef.current?.stop()
      setListening(false)
      return
    }
    const rec = makeRecognition()
    if (!rec) return
    recRef.current = rec
    rec.lang = "kn-IN" // ಕನ್ನಡ — the showpiece; typed Kannada works too
    rec.interimResults = false
    rec.onresult = (ev) => {
      const transcript = Array.from({ length: ev.results.length })
        .map((_, i) => ev.results[i][0]?.transcript ?? "")
        .join(" ")
        .trim()
      if (transcript) {
        setInput(transcript)
        void ask(transcript, "kn")
      }
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    setListening(true)
    rec.start()
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
        eyebrow="Assist · RAG over the FIR corpus"
        title="Intelligence Copilot"
        caption="Plain-English questions over the FIR corpus — every answer grounded in cited records. Citations open the case file."
      />

      <Card className="flex h-[calc(100vh-235px)] min-h-[420px] flex-col">
        <CardContent className="flex min-h-0 flex-1 flex-col gap-3 p-4">
          <div ref={threadRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1.5">
            {CHAT.map((m, i) =>
              m.role === "user" ? (
                <div key={i} className="flex justify-end gap-2.5">
                  <div className="max-w-[70%] rounded-md rounded-br-sm border border-brass/25 bg-brass-soft px-3.5 py-2.5 text-[13px]">
                    {m.text}
                  </div>
                </div>
              ) : (
                <div key={i} className="flex gap-2.5">
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-sm border border-brass/30 bg-brass-soft font-mono text-[9.5px] font-semibold text-brass">
                    AI
                  </div>
                  <div
                    className={cn(
                      "max-w-[82%] rounded-md rounded-tl-sm border border-line-soft bg-panel-2/60 px-3.5 py-2.5",
                      m.res.refused && "border-signal/35",
                      m.pending && "animate-pulse",
                    )}
                  >
                    {m.res.voice && (
                      <div className="mb-2 flex items-start gap-1.5 rounded-sm border border-steel/25 bg-steel-soft/40 px-2 py-1.5 font-mono text-[10.5px] leading-relaxed text-muted-foreground">
                        <Languages className="mt-px size-3 shrink-0 text-steel" />
                        <span>
                          ಕನ್ನಡ: {m.res.voice.original}
                          <span className="mx-1.5 text-faint">→</span>
                          {m.res.voice.english}
                        </span>
                      </div>
                    )}
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
                      <div className="mt-2.5 flex items-start gap-1.5 border-t border-line-soft pt-2 text-[10.5px] text-faint">
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
                className="rounded-sm border border-line bg-panel px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-brass/40 hover:text-foreground"
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
              placeholder="e.g. two-wheeler theft in BNU · ಕನ್ನಡದಲ್ಲಿ ಕೇಳಿ"
              className="bg-panel-2"
              aria-label="Ask the copilot"
            />
            {micSupported.current && (
              <Button
                type="button"
                variant={listening ? "default" : "outline"}
                onClick={toggleMic}
                aria-label={listening ? "Stop listening" : "Ask in Kannada by voice"}
                aria-pressed={listening}
                className={cn(listening && "animate-pulse")}
                title="ಕನ್ನಡ ಧ್ವನಿ — Kannada voice query"
              >
                {listening ? <MicOff className="size-4" /> : <Mic className="size-4" />}
                <span className="hidden sm:inline">{listening ? "Listening…" : "ಕನ್ನಡ"}</span>
              </Button>
            )}
            <Button type="submit">
              <SendHorizonal className="size-4" /> Ask
            </Button>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
