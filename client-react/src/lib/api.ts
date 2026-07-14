import { MOCK } from "@/lib/mock"
import { loadPrincipal } from "@/lib/roles"
import type {
  AbscondingBoard,
  AnomalyAlert,
  AuditEntry,
  CaseFull,
  CopilotResponse,
  DistrictCommandCard,
  EgoGraph,
  EntityDossier,
  Fairness,
  GeoDistrict,
  OfficersRoster,
  OfficerWorklist,
  Ring,
  RiskCell,
  SearchResult,
  Stats,
} from "@/lib/types"

/** Same-origin contract: '' in dev (Vite proxies) and when mounted at /ui/. */
const API = ""

export type DataMode = "live" | "mock"
let mode: DataMode = "live"
const modeSubs = new Set<(m: DataMode) => void>()

/** The topbar badge subscribes here so mock-mode is always visibly disclosed. */
export function subscribeDataMode(fn: (m: DataMode) => void): () => void {
  modeSubs.add(fn)
  fn(mode)
  return () => {
    modeSubs.delete(fn)
  }
}

function setMode(m: DataMode) {
  if (mode !== m) {
    mode = m
    modeSubs.forEach((f) => f(m))
  }
}

/** 403/404 from object reads — screens render the clearance/not-found state. */
export class ApiError extends Error {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

function roleHeaders(json = false): Record<string, string> {
  const p = loadPrincipal()
  const h: Record<string, string> = {
    "X-Actor": p?.actor || "demo",
    "X-Role": p?.role || "analyst",
  }
  if (p?.scope) h["X-Scope"] = p.scope
  if (json) h["Content-Type"] = "application/json"
  return h
}

type MockKey = keyof typeof MOCK

/** Module reads: any failure (offline or error) falls back to fixtures. */
async function jget<T>(path: string, mockKey: MockKey): Promise<T> {
  try {
    const r = await fetch(API + path, { headers: roleHeaders() })
    if (!r.ok) throw new Error(String(r.status))
    setMode("live")
    return (await r.json()) as T
  } catch {
    setMode("mock")
    return MOCK[mockKey] as unknown as T
  }
}

async function jpost<T>(path: string, body: unknown, mockKey: MockKey): Promise<T> {
  try {
    const r = await fetch(API + path, {
      method: "POST",
      headers: roleHeaders(true),
      body: JSON.stringify(body ?? {}),
    })
    if (!r.ok) throw new Error(String(r.status))
    setMode("live")
    return (await r.json()) as T
  } catch {
    setMode("mock")
    return MOCK[mockKey] as unknown as T
  }
}

/** Object reads: keep HTTP error semantics (403 jurisdiction / 404 unknown),
 *  but still fall back to fixtures when the brain is unreachable entirely. */
async function jgetStrict<T>(path: string, mockKey: MockKey): Promise<T> {
  let r: Response
  try {
    r = await fetch(API + path, { headers: roleHeaders() })
  } catch {
    setMode("mock")
    return MOCK[mockKey] as unknown as T
  }
  if (r.ok) {
    setMode("live")
    return (await r.json()) as T
  }
  let detail = ""
  try {
    detail = ((await r.json()) as { detail?: string }).detail ?? ""
  } catch {
    /* non-JSON error body */
  }
  throw new ApiError(r.status, detail)
}

export const api = {
  stats: () => jget<Stats>("/stats", "stats"),
  rings: (top = 6) => jget<{ rings: Ring[] }>(`/network/rings?top=${top}`, "rings"),
  ego: (id: string, radius = 2) =>
    jget<EgoGraph>(`/network/${encodeURIComponent(id)}?radius=${radius}`, "ego"),
  anomalies: () => jpost<{ sample: AnomalyAlert[] }>("/anomaly/run", { write: false }, "anomaly"),
  geoDistricts: () => jget<{ districts: GeoDistrict[] }>("/geo/districts", "geo"),
  riskTop: (n = 10) => jget<{ top: RiskCell[] }>(`/risk/top?n=${n}`, "risktop"),
  fairness: () => jget<Fairness>("/risk/fairness", "fair"),
  copilot: (query: string) =>
    jpost<CopilotResponse>(
      "/copilot",
      { query },
      /guilt|guilty|culprit/i.test(query) ? "copilotRefuse" : "copilot",
    ),
  caseFull: (id: string) => jgetStrict<CaseFull>(`/case/${encodeURIComponent(id)}`, "case"),
  entity: (id: string) => jgetStrict<EntityDossier>(`/entity/${encodeURIComponent(id)}`, "entity"),
  search: (q: string) => jgetStrict<SearchResult>(`/search?q=${encodeURIComponent(q)}`, "search"),
  audit: (limit = 100) => jgetStrict<{ entries: AuditEntry[] }>(`/audit?limit=${limit}`, "audit"),
  districtCommand: (code: string) =>
    jgetStrict<DistrictCommandCard>(`/district/${encodeURIComponent(code)}/command`, "districtCommand"),
  districtRank: () =>
    jgetStrict<{ districts: DistrictCommandCard[] }>("/district/rank", "districtRank"),
  officers: (district?: string) =>
    jgetStrict<OfficersRoster>(
      `/officers${district ? `?district=${encodeURIComponent(district)}` : ""}`,
      "officers",
    ),
  officerCases: (id: string) =>
    jgetStrict<OfficerWorklist>(`/officer/${encodeURIComponent(id)}/cases`, "officerCases"),
  absconding: (opts: { district?: string; gravity?: string; minDays?: number; limit?: number } = {}) => {
    const q = new URLSearchParams()
    if (opts.district) q.set("district", opts.district)
    if (opts.gravity) q.set("gravity", opts.gravity)
    if (opts.minDays) q.set("min_days", String(opts.minDays))
    if (opts.limit) q.set("limit", String(opts.limit))
    const s = q.toString()
    return jgetStrict<AbscondingBoard>(`/absconding${s ? "?" + s : ""}`, "absconding")
  },
}
