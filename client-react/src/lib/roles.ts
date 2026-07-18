import { useSyncExternalStore } from "react"

/** The caller identity sent as X-Actor / X-Role / X-Scope - RBAC + PII masking
 *  are enforced server-side; switching role live is the governance demo. */
export interface Principal {
  actor: string
  name: string
  role: string
  scope: string
}

export interface RolePreset {
  id: string
  role: string
  scope: string
  label: string
  clearance: string
  desc: string
}

/** Clearance-tier presets (blueprint §F1) the login page + role switcher offer. */
export const ROLE_PRESETS: RolePreset[] = [
  {
    id: "scrb-admin",
    role: "scrb-admin",
    scope: "",
    label: "SCRB · Admin",
    clearance: "L5",
    desc: "Statewide, all dossiers & model cards - every read fully audited",
  },
  {
    id: "district-bnu",
    role: "district",
    scope: "BNU",
    label: "District SP · Bengaluru Urban",
    clearance: "L4",
    desc: "Full district incl. dossiers; other districts aggregate-only",
  },
  {
    id: "station-rmn03",
    role: "station",
    scope: "RMN03",
    label: "SHO · Station RMN03",
    clearance: "L2",
    desc: "Own-station cases; no out-of-jurisdiction PII",
  },
  {
    id: "analyst",
    role: "analyst",
    scope: "",
    label: "SCRB · Analyst",
    clearance: "L3",
    desc: "Statewide patterns; victim identities masked (sees “A. M.”)",
  },
  {
    id: "ethics",
    role: "ethics",
    scope: "",
    label: "Ethics · Oversight",
    clearance: "OS",
    desc: "Audit, fairness & model cards only - no case PII at all",
  },
]

export function presetFor(p: Principal | null): RolePreset | undefined {
  return ROLE_PRESETS.find((r) => r.role === p?.role && r.scope === (p?.scope || ""))
}

const KEY = "garuda.principal"
let cached: Principal | null = null
let loadedOnce = false
const subs = new Set<() => void>()

export function loadPrincipal(): Principal | null {
  if (!loadedOnce) {
    loadedOnce = true
    try {
      const raw = sessionStorage.getItem(KEY)
      if (raw) cached = JSON.parse(raw) as Principal
    } catch {
      cached = null
    }
  }
  return cached
}

export function setPrincipal(p: Principal | null) {
  cached = p
  loadedOnce = true
  try {
    if (p) sessionStorage.setItem(KEY, JSON.stringify(p))
    else sessionStorage.removeItem(KEY)
  } catch {
    /* storage unavailable - session-only state still works */
  }
  subs.forEach((f) => f())
}

function subscribe(fn: () => void) {
  subs.add(fn)
  return () => {
    subs.delete(fn)
  }
}

export function usePrincipal(): Principal | null {
  return useSyncExternalStore(subscribe, loadPrincipal)
}

export function initials(p: Principal | null): string {
  const n = (p?.name || p?.actor || "??").trim()
  const parts = n.split(/\s+/)
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || parts[0]?.[1] || "")).toUpperCase()
}
