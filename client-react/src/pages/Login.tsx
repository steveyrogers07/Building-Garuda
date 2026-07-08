import { Fingerprint, Lock, ShieldCheck } from "lucide-react"
import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { ClassificationBar } from "@/components/brand/ClassificationBar"
import { KspCrest } from "@/components/brand/KspCrest"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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

/** Government-grade sign-in: crest, classification, clearance selection.
 *  Locally this is a stub principal (headers drive server-side RBAC);
 *  on Catalyst the same form fronts the Web SDK. */
export default function Login() {
  const navigate = useNavigate()
  const [officerId, setOfficerId] = useState("sr")
  const [password, setPassword] = useState("")
  const [presetId, setPresetId] = useState("scrb-admin")
  const preset = ROLE_PRESETS.find((r) => r.id === presetId)!

  function submit(e: FormEvent) {
    e.preventDefault()
    const id = officerId.trim()
    if (!id) return
    setPrincipal({ actor: id, name: id.toUpperCase(), role: preset.role, scope: preset.scope })
    toast(`Signed in — ${preset.label}`, {
      description: "All access under this clearance is logged to the audit trail.",
    })
    navigate("/")
  }

  return (
    <div className="grid-field flex min-h-screen flex-col bg-background">
      <ClassificationBar />

      <div className="flex flex-1 items-center justify-center px-4 py-10">
        <div className="w-full max-w-[420px]">
          {/* identity block */}
          <div className="mb-7 text-center">
            <KspCrest size={92} className="mx-auto text-amber drop-shadow-[0_0_18px_rgba(249,168,37,0.25)]" />
            <h1 className="mt-4 font-mono text-[30px] font-bold tracking-[0.3em] text-foreground">
              GARUDA
            </h1>
            <div className="mt-1 text-[13px] text-muted-foreground">
              ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ · Karnataka State Police
            </div>
            <div className="k-label mt-1.5">State Crime Records Bureau — Crime Intelligence Platform</div>
          </div>

          <form
            onSubmit={submit}
            className="rounded-lg border bg-card/90 p-6 shadow-pop backdrop-blur"
          >
            <div className="flex items-center gap-2">
              <Fingerprint className="size-4 text-primary" />
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
              className="mb-3.5 bg-surface-2 font-mono"
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
              className="mb-3.5 bg-surface-2 font-mono"
              placeholder="••••••••"
            />

            <label className="k-label mb-1.5 block">Clearance</label>
            <Select value={presetId} onValueChange={setPresetId}>
              <SelectTrigger className="w-full bg-surface-2" aria-label="Clearance tier">
                <SelectValue />
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
            <p className="mt-1.5 min-h-8 text-[11px] leading-snug text-faint">{preset.desc}</p>

            <Button type="submit" className="mt-3 w-full font-mono tracking-wider">
              <Lock className="size-3.5" /> AUTHENTICATE
            </Button>

            <div className="mt-4 flex items-start gap-2 rounded-md border border-border-soft bg-surface-2/60 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-ok" />
              <span>
                Access is clearance-gated and fully audited. GARUDA surfaces and explains records —
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
