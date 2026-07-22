import { Fingerprint, Lock, ShieldCheck } from "lucide-react"
import { useEffect, useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

declare global {
  interface Window {
    /** Catalyst embedded-auth SDK - injected only when the SPA is served via
     *  Web Client Hosting with Authentication enabled (plan §4.4). */
    catalyst?: { auth?: { isUserAuthenticated?: () => Promise<unknown> } }
  }
}

import { ClassificationBar } from "@/components/brand/ClassificationBar"
import { KspCrest } from "@/components/brand/KspCrest"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { ROLE_PRESETS, setPrincipal } from "@/lib/roles"

/** The shared demo credentials, in one place. They appear in the arrival
 *  dialog, in the notice under the form, and in the submit check, and three
 *  hand-maintained copies is how a password ends up printed on screen that
 *  no longer opens the door. */
const DEMO_ID = "garudaadmin"
const DEMO_PASSWORD = "datathon26"

/** Government-grade sign-in: crest, classification, clearance selection.
 *  Locally this is a stub principal (headers drive server-side RBAC);
 *  on Catalyst the same form fronts the Web SDK. */
export default function Login() {
  const navigate = useNavigate()
  const [officerId, setOfficerId] = useState("")
  const [password, setPassword] = useState("")
  const [presetId, setPresetId] = useState("scrb-admin")
  const [catalystReady, setCatalystReady] = useState(false)
  // Evaluators arrive on a link with no context. The access notice under the
  // form was being missed entirely - it sits below the fold on a laptop - so
  // the same credentials lead with a dismissable card. It defaults open once
  // per tab: helpful on arrival, never nagging on a re-visit or after signing
  // out, which is why the flag lives in sessionStorage rather than state alone.
  const [credsOpen, setCredsOpen] = useState(
    () => sessionStorage.getItem("garuda.creds.seen") !== "1",
  )

  function dismissCreds() {
    sessionStorage.setItem("garuda.creds.seen", "1")
    setCredsOpen(false)
  }

  /** One click from "I have a link" to "I am looking at the console". */
  function fillDemoCredentials() {
    setOfficerId(DEMO_ID)
    setPassword(DEMO_PASSWORD)
    dismissCreds()
  }

  const preset = ROLE_PRESETS.find((r) => r.id === presetId)!

  // Catalyst path (plan §4.4): when the embedded-auth SDK is present, an
  // existing Zoho session maps to a GARUDA principal via GET /whoami
  // (Console_Users resolves role/scope server-side). Absent the SDK - local
  // dev, or the AppSail-served build - nothing changes: the demo login below
  // IS the governance demo and stays.
  useEffect(() => {
    const auth = window.catalyst?.auth
    if (!auth?.isUserAuthenticated) return
    setCatalystReady(true)
    auth
      .isUserAuthenticated()
      .then(async (u) => {
        if (!u) return
        const r = await fetch("/whoami", { credentials: "include" })
        if (!r.ok) return
        const me = await r.json()
        if (!me.role) return
        setPrincipal({ actor: me.actor, name: me.display_name || me.actor,
                       role: me.role, scope: me.scope || "" })
        toast(`Signed in - ${me.display_name || me.actor}`, {
          description: "Verified Catalyst identity; clearance from Console_Users.",
        })
        navigate("/")
      })
      .catch(() => { /* fall through to the demo form */ })
  }, [navigate])

  const [authError, setAuthError] = useState("")

  function submit(e: FormEvent) {
    e.preventDefault()
    const id = officerId.trim()
    if (!id) return
    // Demo-phase gate: one shared credential pair keeps idle visitors out of a
    // public dev URL. This is a UI courtesy, not the security boundary - real
    // sign-in is Catalyst Authentication + Console_Users role mapping (built,
    // activates with the API Gateway).
    if (id.toLowerCase() !== DEMO_ID || password !== DEMO_PASSWORD) {
      setAuthError("Invalid credentials. Demo evaluators: use the access details in the notice below.")
      return
    }
    setAuthError("")
    setPrincipal({ actor: id, name: id.toUpperCase(), role: preset.role, scope: preset.scope })
    toast(`Signed in - ${preset.label}`, {
      description: "All access under this clearance is logged to the audit trail.",
    })
    navigate("/")
  }

  return (
    <div className="grid-field flex min-h-screen flex-col bg-background">
      <ClassificationBar />

      {/* Arrival card. DialogContent renders its own close control top-right. */}
      <Dialog open={credsOpen} onOpenChange={(o) => (o ? setCredsOpen(true) : dismissCreds())}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogHeader>
            <div className="mb-1 flex items-center gap-2">
              <Badge variant="outline" className="border-brass/40 text-brass">
                Demo evaluation access
              </Badge>
            </div>
            <DialogTitle className="t-display text-[19px] tracking-[0.1em]">
              Sign in to GARUDA
            </DialogTitle>
            <DialogDescription className="text-[12px] leading-relaxed">
              Use these credentials to explore the console. Any of the five clearance
              tiers will sign you in, and each demonstrates its own jurisdiction gates
              and PII masking.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 rounded-sm border border-brass/30 bg-brass-soft/40 px-3.5 py-3">
            <div className="flex items-center justify-between gap-4">
              <span className="k-label">Officer ID</span>
              <span className="select-all font-mono text-[13.5px] font-semibold text-foreground">
                {DEMO_ID}
              </span>
            </div>
            <Separator className="bg-brass/15" />
            <div className="flex items-center justify-between gap-4">
              <span className="k-label">Password</span>
              <span className="select-all font-mono text-[13.5px] font-semibold text-foreground">
                {DEMO_PASSWORD}
              </span>
            </div>
          </div>

          <Button onClick={fillDemoCredentials} className="w-full gap-2">
            <Lock className="size-3.5" /> Fill in and continue
          </Button>

          <p className="text-center font-mono text-[10.5px] leading-relaxed text-faint">
            Demonstration build on synthetic data. No real FIR record or person
            appears anywhere in this system.
          </p>
        </DialogContent>
      </Dialog>

      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-[420px]">
          {/* identity block */}
          <div className="mb-7 text-center">
            <KspCrest size={92} className="mx-auto text-brass drop-shadow-[0_0_18px_rgba(201,162,39,0.25)]" />
            <h1 className="t-display mt-4 text-[42px] leading-none tracking-[0.24em] text-foreground">
              GARUDA
            </h1>
            <div className="mt-1.5 text-[13px] text-muted-foreground">
              ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ · Karnataka State Police
            </div>
            <div className="k-label mt-1.5">State Crime Records Bureau - Crime Intelligence Platform</div>
          </div>

          <form
            onSubmit={submit}
            className="rounded-md border border-line bg-card/90 p-6 shadow-pop backdrop-blur"
          >
            <div className="flex items-center gap-2">
              <Fingerprint className="size-4 text-brass" />
              <span className="k-label text-muted-foreground">Secure sign-in</span>
            </div>
            <Separator className="my-4" />

            <label className="k-label mb-1.5 block" htmlFor="officer-id">
              Officer ID
            </label>
            <Input
              id="officer-id"
              value={officerId}
              onChange={(e) => setOfficerId(e.target.value)}
              autoComplete="username"
              className="mb-3.5 bg-panel-2 font-mono"
              placeholder="KSP officer id"
            />

            <label className="k-label mb-1.5 block" htmlFor="password">
              Password
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="mb-3.5 bg-panel-2 font-mono"
              placeholder="••••••••"
            />

            <label className="k-label mb-1.5 block">Clearance</label>
            <Select value={presetId} onValueChange={setPresetId}>
              <SelectTrigger className="w-full bg-panel-2" aria-label="Clearance tier">
                <SelectValue />
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
            <p className="mt-1.5 min-h-8 text-[11px] leading-snug text-faint">{preset.desc}</p>

            <Button type="submit" className="t-display mt-3 w-full text-[15px] tracking-[0.14em]">
              <Lock className="size-3.5" /> Authenticate
            </Button>

            {catalystReady && (
              <Button
                type="button"
                variant="outline"
                className="mt-2 w-full text-[13px]"
                onClick={() => {
                  // Catalyst's hosted login (served by the platform when
                  // Authentication is enabled); returns here with a session.
                  window.location.href = "/__catalyst/auth/login"
                }}
              >
                <ShieldCheck className="size-3.5" /> Sign in with Zoho Catalyst
              </Button>
            )}

            {authError && (
              <div className="mt-2 rounded-sm border border-signal/40 bg-signal/10 px-3 py-2 text-[11.5px] text-signal">
                {authError}
              </div>
            )}

            <div className="mt-4 rounded-sm border border-brass/30 bg-brass-soft/50 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
              <span className="k-label text-brass">Demo evaluation access</span>
              <div className="mt-1">
                Officer ID <b className="font-mono text-foreground">{DEMO_ID}</b> · Password{" "}
                <b className="font-mono text-foreground">{DEMO_PASSWORD}</b> - pick any clearance
                tier to experience its jurisdiction gates and PII masking.
              </div>
              <div className="mt-1 text-faint">
                Production sign-in (Zoho Catalyst Authentication → Console_Users role mapping) is
                built and activates with the API Gateway.
              </div>
            </div>

            <div className="mt-2 flex items-start gap-2 rounded-sm border border-line-soft bg-panel-2/60 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-ok" />
              <span>
                Access is clearance-gated and fully audited. GARUDA surfaces and explains records -
                it never asserts guilt.
              </span>
            </div>
          </form>

          <div className="mt-5 text-center font-mono text-[10.5px] leading-relaxed text-faint">
            Authorized personnel only · Unauthorized access is an offence
            <br />
            Government of Karnataka · Demonstration build on synthetic data
          </div>
        </div>
      </div>
    </div>
  )
}
