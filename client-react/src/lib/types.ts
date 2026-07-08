/** API contract types — mirrors app/routers/analytics.py responses. */

export type EntityType = "person" | "vehicle" | "phone"

export interface Stats {
  incidents: number
  entities: number
  districts: number
  crime_types: number
  by_crime: [string, number][]
}

export interface Ring {
  kingpin_id: string
  kingpin_label: string
  persons: number
  districts: string[]
  district_count: number
  incident_count: number
  shared_links: string[]
}

export interface GraphNode {
  id: string
  label: string
  type: string
  strength?: number
  betweenness?: number
  community?: number
  incident_count?: number
  districts?: string[]
}

export interface GraphEdge {
  source: string
  target: string
  weight?: number
  kinds?: string[]
}

export interface EgoGraph {
  center?: string
  node_count?: number
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface AnomalyAlert {
  crime_type: string
  district_code: string
  window_start: string
  severity: string
  z_score?: number
  ratio?: number
  detail?: string
}

export interface GeoDistrict {
  code: string
  name?: string
  incidents: number
  lat: number
  lng: number
  top_crime?: string
}

export interface RiskCell {
  district_code: string
  crime_type: string
  risk_score: number
  top_drivers: string | string[]
  model_version?: string
}

export interface FairnessWard {
  area_code: string
  ratio: number
  over_predicted: boolean
}

export interface Fairness {
  summary: { wards?: number; over_predicted?: number; flag_ratio?: number; max_ratio?: number }
  wards: FairnessWard[]
}

export interface Citation {
  fir_no?: string
  incident_id: string
  crime_type?: string
  district_code?: string
  occurred_at?: string
  snippet?: string
}

export interface CopilotResponse {
  answer: string
  citations: Citation[]
  guardrail?: string
  refused?: boolean
  reason?: string
}

export interface Party {
  role: string
  entity_id?: string
  canonical_id?: string
  type: string
  value: string
  masked?: string | null
  age?: string
  evidence_type?: string
  note?: string
}

export interface LinkReason {
  type: string
  detail: string
}

export interface LinkedCase {
  incident_id: string
  fir_no?: string
  crime_type?: string
  district_code?: string
  occurred_at?: string
  strength: number
  reasons: LinkReason[]
}

export interface Incident {
  incident_id: string
  fir_no?: string
  occurred_at?: string
  reported_at?: string
  district_code?: string
  station_code?: string
  crime_type?: string
  ipc_bns_code?: string
  address_text?: string
  mo_text?: string
  status?: string
  case_category?: string   // FIR | UDR | PAR | Zero-FIR (organizer CaseCategory)
  gravity?: string         // Heinous | Non-Heinous (organizer GravityOffence)
}

export interface CaseOfficer {
  name?: string
  rank?: string
  designation?: string
}

export interface CaseChargesheet {
  cs_type: string   // A=Chargesheet | B=False Case | C=Undetected
  cs_date?: string
}

export interface CaseFull {
  incident: Incident
  protected?: boolean
  series_id?: string | null
  parties: Party[]
  linked_cases: LinkedCase[]
  timeline?: { ts: string; label: string }[]
  officer?: CaseOfficer | null
  chargesheet?: CaseChargesheet | null
  viewer?: { role: string; scope?: string | null }
  error?: string
}

export interface DistrictOutcomes {
  A: number
  B: number
  C: number
}

export interface OfficerRow {
  officer_id: string
  name: string
  rank?: string
  cases: number
  chargesheeted: number
  clearance_rate: number | null
}

export interface DistrictCommandCard {
  district_code: string
  total_incidents: number
  open: number
  disposed: number
  backlog_aging: number
  backlog_threshold_days: number
  outcomes: DistrictOutcomes
  outcomes_total: number
  clearance_rate: number | null
  top_crimes: [string, number][]
  top_officers: OfficerRow[]
}

export interface Appearance {
  incident_id: string
  fir_no?: string
  role: string
  crime_type?: string
  district_code?: string
  occurred_at?: string
  status?: string
}

export interface Associate {
  canonical_id: string
  label: string
  type: string
  weight: number
  kinds?: string[]
  masked?: string | null
}

export interface EntityDossier {
  canonical_id: string
  type: string
  value: string
  masked?: string | null
  aliases?: { value: string }[]
  stats?: {
    incidents?: number
    districts?: string[]
    first_seen?: string
    last_seen?: string
    roles?: Record<string, number>
  }
  appearances?: Appearance[]
  associates?: Associate[]
  timeline?: { month: string; count: number }[]
  indicators?: {
    incident_count?: number
    district_span?: number
    active_month_max?: number
    recent_month_incidents?: number
  }
  guardrail?: string
  error?: string
}

export interface SearchEntityHit {
  canonical_id: string
  value: string
  type: string
  incidents?: number
  districts?: string[]
  masked?: string | null
}

export interface SearchCaseHit {
  incident_id: string
  fir_no?: string
  crime_type?: string
  district_code?: string
  occurred_at?: string
  status?: string
  snippet?: string
}

export interface SearchResult {
  query?: string
  took_ms?: number
  groups?: {
    cases?: SearchCaseHit[]
    people?: SearchEntityHit[]
    vehicles?: SearchEntityHit[]
    phones?: SearchEntityHit[]
    places?: { code: string; incidents?: number }[]
  }
  semantic?: SearchCaseHit[]
  note?: string
}

export interface AuditEntry {
  ts?: string
  actor?: string
  role?: string
  action?: string
  resource?: string
  query?: string
  [k: string]: unknown
}
