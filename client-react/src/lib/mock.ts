/** Planted-scenario fixtures (the KA68MC3164 ring) — served whenever the brain
 *  is unreachable so the console always renders. Ported from client/assets/app.js. */

export const MOCK = {
  stats: {
    incidents: 10130,
    entities: 14608,
    districts: 31,
    crime_types: 16,
    by_crime: [
      ["Two-wheeler theft", 1642],
      ["Theft", 1380],
      ["House burglary", 1325],
      ["Chain snatching", 1037],
      ["Assault", 834],
      ["Cheating", 727],
      ["Robbery", 624],
      ["Motor vehicle theft", 534],
    ] as [string, number][],
  },

  rings: {
    rings: [
      {
        kingpin_id: "ENT014602",
        kingpin_label: "Aayush Zachariah",
        persons: 5,
        districts: ["BNU", "KLR", "RMN", "TMK"],
        district_count: 4,
        incident_count: 10,
        shared_links: ["+916534933629", "KA68MC3164"],
      },
    ],
  },

  ego: {
    center: "ENT014602",
    node_count: 7,
    nodes: [
      { id: "ENT014602", label: "Aayush Zachariah", type: "person", strength: 31, betweenness: 0, community: 0, incident_count: 9, districts: ["BNU", "RMN", "TMK", "KLR"] },
      { id: "ENT014603", label: "Joshua Dhar", type: "person", strength: 15, community: 0, incident_count: 4, districts: ["BNU", "TMK"] },
      { id: "ENT014604", label: "Urvi Amble", type: "person", strength: 18, community: 0, incident_count: 5, districts: ["BNU", "KLR"] },
      { id: "ENT014605", label: "Imaran Pal", type: "person", strength: 14, community: 0, incident_count: 4, districts: ["RMN"] },
      { id: "ENT014606", label: "Wyatt Thaker", type: "person", strength: 2, community: 0, incident_count: 1, districts: ["TMK"] },
      { id: "ENT014607", label: "+916534933629", type: "phone", strength: 33, community: 0, incident_count: 10, districts: ["BNU", "RMN", "TMK", "KLR"] },
      { id: "ENT014608", label: "KA68MC3164", type: "vehicle", strength: 33, community: 0, incident_count: 10, districts: ["BNU", "RMN", "TMK", "KLR"] },
    ],
    edges: [
      ["ENT014602", "ENT014603"], ["ENT014602", "ENT014604"], ["ENT014602", "ENT014607"],
      ["ENT014602", "ENT014608"], ["ENT014603", "ENT014607"], ["ENT014604", "ENT014608"],
      ["ENT014605", "ENT014607"], ["ENT014606", "ENT014608"], ["ENT014604", "ENT014607"],
      ["ENT014603", "ENT014608"],
    ].map(([source, target]) => ({ source, target, weight: 3, kinds: ["co_offence"] })),
  },

  anomaly: {
    sample: [
      { crime_type: "House burglary", district_code: "BNU", window_start: "2025-04-01", severity: "high", z_score: 16.9, ratio: 4.8, detail: "House burglary in BNU 2025-04: 63 incidents vs baseline 13/mo (×4.8, z=16.9)" },
      { crime_type: "Two-wheeler theft", district_code: "BNU", window_start: "2025-03-01", severity: "high", z_score: 12.1, ratio: 4.0, detail: "Two-wheeler theft in BNU 2025-03: 72 vs baseline 18/mo (×4.0, z=12.1)" },
      { crime_type: "Two-wheeler theft", district_code: "MYS", window_start: "2024-09-01", severity: "high", z_score: 11.5, ratio: 5.2, detail: "Two-wheeler theft in MYS 2024-09: 21 vs baseline 4/mo (×5.2, z=11.5)" },
    ],
  },

  geo: {
    districts: [
      { code: "BNU", name: "Bengaluru Urban", incidents: 980, lat: 12.97, lng: 77.59, top_crime: "Two-wheeler theft" },
      { code: "MYS", name: "Mysuru", incidents: 410, lat: 12.31, lng: 76.65, top_crime: "House burglary" },
      { code: "BEL", name: "Belagavi", incidents: 360, lat: 15.85, lng: 74.5, top_crime: "Theft" },
      { code: "KLB", name: "Kalaburagi", incidents: 300, lat: 17.33, lng: 76.83, top_crime: "Assault" },
      { code: "TMK", name: "Tumakuru", incidents: 280, lat: 13.34, lng: 77.1, top_crime: "Chain snatching" },
      { code: "RMN", name: "Ramanagara", incidents: 240, lat: 12.72, lng: 77.28, top_crime: "Chain snatching" },
      { code: "KLR", name: "Kolar", incidents: 220, lat: 13.13, lng: 78.13, top_crime: "Chain snatching" },
      { code: "DK", name: "Dakshina Kannada", incidents: 260, lat: 12.87, lng: 75.0, top_crime: "Cheating" },
    ],
  },

  risktop: {
    top: [
      { district_code: "BNU", crime_type: "Theft", risk_score: 0.42, top_drivers: '["roll_28","population","crime_code"]', model_version: "lgbm-p6-v1" },
      { district_code: "BNU", crime_type: "Two-wheeler theft", risk_score: 0.41, top_drivers: '["roll_28","urbanization","dow"]', model_version: "lgbm-p6-v1" },
      { district_code: "MYS", crime_type: "House burglary", risk_score: 0.33, top_drivers: '["lag_7","density","month"]', model_version: "lgbm-p6-v1" },
    ],
  },

  fair: {
    summary: { wards: 31, over_predicted: 4, flag_ratio: 1.3, max_ratio: 1.61 },
    wards: [
      { area_code: "BNU", ratio: 1.61, over_predicted: true },
      { area_code: "MYS", ratio: 1.44, over_predicted: true },
      { area_code: "BEL", ratio: 1.38, over_predicted: true },
      { area_code: "DK", ratio: 1.33, over_predicted: true },
      { area_code: "KLB", ratio: 1.18, over_predicted: false },
      { area_code: "TMK", ratio: 1.02, over_predicted: false },
      { area_code: "RMN", ratio: 0.94, over_predicted: false },
      { area_code: "KLR", ratio: 0.81, over_predicted: false },
    ],
  },

  copilot: {
    answer: "Found matching FIR records. Top results are cited below — these surface records, not determinations of guilt.",
    citations: [
      { fir_no: "BNU20/2024/0028", incident_id: "INC010001", crime_type: "Chain snatching", district_code: "BNU", occurred_at: "2024-01-24", snippet: "Gold chain snatched near MG Road; accused fled on a two-wheeler bearing KA68MC3164." },
      { fir_no: "RMN03/2024/0011", incident_id: "INC010003", crime_type: "Chain snatching", district_code: "RMN", occurred_at: "2024-03-08", snippet: "Two miscreants snatched a chain and sped away; call record links +916534933629." },
    ],
    guardrail: "This system surfaces FIR records matching the query; it does not determine guilt.",
  },

  copilotRefuse: {
    refused: true,
    reason: "guilt_determination",
    answer: "This system surfaces FIR records matching the query; it does not determine guilt. Persons named are as recorded in the FIR, pending investigation/trial.",
    citations: [],
    guardrail: "Surfaces records, never asserts guilt.",
  },

  search: {
    query: "",
    took_ms: 3,
    groups: {
      cases: [
        { incident_id: "INC010001", fir_no: "BNU20/2024/0028", crime_type: "Chain snatching", district_code: "BNU", occurred_at: "2024-01-24", status: "Under Investigation" },
      ],
      people: [
        { canonical_id: "ENT014602", value: "Aayush Zachariah", type: "person", incidents: 9, districts: ["BNU", "KLR", "RMN", "TMK"] },
      ],
      vehicles: [
        { canonical_id: "ENT014608", value: "KA68MC3164", type: "vehicle", incidents: 10, districts: ["BNU", "KLR", "RMN", "TMK"] },
      ],
      phones: [
        { canonical_id: "ENT014607", value: "+916534933629", type: "phone", incidents: 10, districts: ["BNU", "KLR", "RMN", "TMK"] },
      ],
      places: [],
    },
    semantic: [],
  },

  entity: {
    canonical_id: "ENT014602",
    type: "person",
    value: "Aayush Zachariah",
    masked: null,
    aliases: [],
    stats: { incidents: 9, districts: ["BNU", "KLR", "RMN", "TMK"], first_seen: "2024-01-24", last_seen: "2024-11-02", roles: { suspect: 9 } },
    appearances: [
      { incident_id: "INC010001", fir_no: "BNU20/2024/0028", role: "suspect", crime_type: "Chain snatching", district_code: "BNU", occurred_at: "2024-01-24", status: "Under Investigation" },
      { incident_id: "INC010003", fir_no: "RMN03/2024/0011", role: "suspect", crime_type: "Chain snatching", district_code: "RMN", occurred_at: "2024-03-08", status: "Under Investigation" },
    ],
    associates: [
      { canonical_id: "ENT014607", label: "+916534933629", type: "phone", weight: 9, kinds: ["shared_phone"] },
      { canonical_id: "ENT014608", label: "KA68MC3164", type: "vehicle", weight: 9, kinds: ["shared_vehicle"] },
      { canonical_id: "ENT014604", label: "Urvi Amble", type: "person", weight: 5, kinds: ["co_offence"] },
    ],
    timeline: [
      { month: "2024-01", count: 1 },
      { month: "2024-03", count: 2 },
      { month: "2024-06", count: 3 },
      { month: "2024-09", count: 2 },
      { month: "2024-11", count: 1 },
    ],
    indicators: { incident_count: 9, district_span: 4, active_month_max: 3, recent_month_incidents: 1 },
    guardrail: "Activity indicators describe recorded involvement only; no determination of guilt is made or implied.",
    viewer: { role: "demo", scope: null },
  },

  case: {
    incident: {
      incident_id: "INC010002",
      fir_no: "RMN03/2024/0007",
      occurred_at: "2024-02-12 21:40:00",
      reported_at: "2024-02-13 09:15:00",
      district_code: "RMN",
      station_code: "RMN03",
      crime_type: "Chain snatching",
      ipc_bns_code: "304(2)",
      address_text: "Old Market Road, Ramanagara",
      mo_text: "Two miscreants on a motorcycle snatched a gold chain and sped away. CCTV places vehicle KA68MC3164 at the scene; call records link +916534933629.",
      status: "Under Investigation",
      case_category: "FIR",
      gravity: "Non-Heinous",
    },
    protected: false,
    series_id: null,
    officer: { name: "Vinaya Sodhi", rank: "PSI", designation: "Investigating Officer" },
    chargesheet: null,
    deadline: { window_days: 60, arrest_date: "2025-05-25", due_date: "2025-07-24", days_remaining: 24, bucket: "amber", arrested: 1 },
    parties: [
      { role: "suspect", entity_id: "ENT014602", canonical_id: "ENT014602", type: "person", value: "Aayush Zachariah", age: "29", evidence_type: "cctv", note: "as recorded in the FIR; pending investigation/trial" },
      { role: "victim", entity_id: "ENTV", canonical_id: "ENTV", type: "person", value: "M. R.", masked: "jurisdiction", evidence_type: "fir_named" },
      { role: "vehicle_used", entity_id: "ENT014608", canonical_id: "ENT014608", type: "vehicle", value: "KA68MC3164", evidence_type: "cctv" },
      { role: "phone_used", entity_id: "ENT014607", canonical_id: "ENT014607", type: "phone", value: "+916534933629", evidence_type: "call_record" },
    ],
    linked_cases: [
      {
        incident_id: "INC010001",
        fir_no: "BNU20/2024/0028",
        crime_type: "Chain snatching",
        district_code: "BNU",
        occurred_at: "2024-01-24",
        strength: 11,
        reasons: [
          { type: "shared_vehicle", detail: "vehicle: KA68MC3164" },
          { type: "shared_phone", detail: "phone: +916534933629" },
          { type: "shared_person", detail: "person: Aayush Zachariah" },
        ],
      },
    ],
    timeline: [
      { ts: "2024-02-12 21:40:00", label: "Incident occurred" },
      { ts: "2024-02-13 09:15:00", label: "FIR registered" },
      { ts: "2025-05-25", label: "Accused in custody — default-bail clock starts" },
      { ts: "2025-07-24", label: "Chargesheet due — 24d left before default bail" },
    ],
    viewer: { role: "demo", scope: null },
  },

  districtCommand: {
    district_code: "BNU",
    total_incidents: 980,
    open: 441,
    disposed: 539,
    backlog_aging: 96,
    backlog_threshold_days: 90,
    outcomes: { A: 312, B: 41, C: 84 },
    outcomes_total: 437,
    clearance_rate: 0.714,
    top_crimes: [["Two-wheeler theft", 312], ["Theft", 198], ["House burglary", 176], ["Chain snatching", 121], ["Assault", 88]],
    top_officers: [
      { officer_id: "OFF0114", name: "Vinaya Sodhi", rank: "PSI", cases: 39, chargesheeted: 11, clearance_rate: 0.846 },
      { officer_id: "OFF0054", name: "Ramesh Achar", rank: "PI", cases: 34, chargesheeted: 22, clearance_rate: 0.786 },
      { officer_id: "OFF0201", name: "Kavya Hegde", rank: "ASI", cases: 29, chargesheeted: 15, clearance_rate: 0.652 },
    ],
  },

  districtRank: {
    districts: [
      { district_code: "BGK", total_incidents: 210, open: 80, disposed: 130, backlog_aging: 12, backlog_threshold_days: 90, outcomes: { A: 88, B: 6, C: 12 }, outcomes_total: 106, clearance_rate: 0.831, top_crimes: [], top_officers: [] },
      { district_code: "BNU", total_incidents: 980, open: 441, disposed: 539, backlog_aging: 96, backlog_threshold_days: 90, outcomes: { A: 312, B: 41, C: 84 }, outcomes_total: 437, clearance_rate: 0.714, top_crimes: [], top_officers: [] },
      { district_code: "MYS", total_incidents: 410, open: 190, disposed: 220, backlog_aging: 34, backlog_threshold_days: 90, outcomes: { A: 132, B: 22, C: 40 }, outcomes_total: 194, clearance_rate: 0.680, top_crimes: [], top_officers: [] },
      { district_code: "KLB", total_incidents: 300, open: 160, disposed: 140, backlog_aging: 41, backlog_threshold_days: 90, outcomes: { A: 71, B: 18, C: 39 }, outcomes_total: 128, clearance_rate: 0.555, top_crimes: [], top_officers: [] },
    ],
  },

  // First roster row must match the officerCases fixture — offline mode selects
  // officers[0] and renders that worklist.
  officers: {
    as_of: "2025-06-30",
    officers: [
      { officer_id: "OFF0114", name: "Vinaya Sodhi", rank: "PSI", district_code: "BNU", unit_code: "BNU07", open: 4, urgent: 2 },
      { officer_id: "OFF0097", name: "Kashvi Sule", rank: "Head Constable", district_code: "HVR", unit_code: "HVR02", open: 92, urgent: 19 },
      { officer_id: "OFF0054", name: "Ramesh Achar", rank: "PI", district_code: "RMN", unit_code: "RMN03", open: 33, urgent: 7 },
      { officer_id: "OFF0201", name: "Kavya Hegde", rank: "ASI", district_code: "MYS", unit_code: "MYS04", open: 26, urgent: 3 },
    ],
  },

  officerCases: {
    officer: { officer_id: "OFF0114", name: "Vinaya Sodhi", rank: "PSI", designation: "Investigating Officer", district_code: "BNU", unit_code: "BNU07" },
    as_of: "2025-06-30",
    summary: { open: 4, overdue: 1, red: 1, amber: 1, green: 0, no_clock: 1, heinous: 1 },
    cases: [
      { incident_id: "INC010004", fir_no: "BNU07/2024/0083", crime_type: "Robbery", district_code: "BNU", station_code: "BNU07", occurred_at: "2024-11-19", status: "Under Investigation", gravity: "Heinous", case_age_days: 223, deadline: { window_days: 90, arrest_date: "2025-03-14", due_date: "2025-06-12", days_remaining: -18, bucket: "overdue", arrested: 2 } },
      { incident_id: "INC010005", fir_no: "BNU07/2025/0016", crime_type: "House burglary", district_code: "BNU", station_code: "BNU07", occurred_at: "2025-03-02", status: "Under Investigation", gravity: "Non-Heinous", case_age_days: 120, deadline: { window_days: 60, arrest_date: "2025-05-06", due_date: "2025-07-05", days_remaining: 5, bucket: "red", arrested: 1 } },
      { incident_id: "INC010002", fir_no: "RMN03/2024/0007", crime_type: "Chain snatching", district_code: "RMN", station_code: "RMN03", occurred_at: "2024-02-12", status: "Under Investigation", gravity: "Non-Heinous", case_age_days: 504, deadline: { window_days: 60, arrest_date: "2025-05-25", due_date: "2025-07-24", days_remaining: 24, bucket: "amber", arrested: 1 } },
      { incident_id: "INC010006", fir_no: "BNU07/2025/0042", crime_type: "Cheating", district_code: "BNU", station_code: "BNU07", occurred_at: "2025-05-28", status: "Under Investigation", gravity: "Non-Heinous", case_age_days: 33, deadline: null },
    ],
  },

  absconding: {
    as_of: "2025-06-30",
    summary: { people: 1732, cases: 2124, heinous_people: 186, districts: 31, total_pairs_unfiltered: 2124 },
    people: [
      {
        canonical_id: "ENT014602",
        name: "Aayush Zachariah",
        case_count: 3,
        max_days_open: 523,
        heinous: true,
        districts: ["BNU", "KLR", "RMN", "TMK"],
        cases: [
          { incident_id: "INC010001", fir_no: "BNU20/2024/0028", crime_type: "Chain snatching", district_code: "BNU", station_code: "BNU20", gravity: "Non-Heinous", status: "Under Investigation", occurred_at: "2024-01-24", days_open: 523 },
          { incident_id: "INC010004", fir_no: "BNU07/2024/0083", crime_type: "Robbery", district_code: "BNU", station_code: "BNU07", gravity: "Heinous", status: "Under Investigation", occurred_at: "2024-11-19", days_open: 223 },
          { incident_id: "INC010003", fir_no: "RMN03/2024/0011", crime_type: "Chain snatching", district_code: "RMN", station_code: "RMN03", gravity: "Non-Heinous", status: "Under Investigation", occurred_at: "2024-03-08", days_open: 479 },
        ],
      },
      {
        canonical_id: "ENT014605",
        name: "Imaran Pal",
        case_count: 2,
        max_days_open: 479,
        heinous: false,
        districts: ["RMN"],
        cases: [
          { incident_id: "INC010003", fir_no: "RMN03/2024/0011", crime_type: "Chain snatching", district_code: "RMN", station_code: "RMN03", gravity: "Non-Heinous", status: "Under Investigation", occurred_at: "2024-03-08", days_open: 479 },
          { incident_id: "INC010007", fir_no: "RMN03/2024/0029", crime_type: "Theft", district_code: "RMN", station_code: "RMN03", gravity: "Non-Heinous", status: "Pending Trial", occurred_at: "2024-08-15", days_open: 318 },
        ],
      },
    ],
    guardrail: "Persons listed are suspects named in FIRs on open cases with no recorded arrest; inclusion is not a determination of guilt.",
  },

  audit: {
    entries: [
      { ts: "2026-07-02 10:12:04", actor: "sr", role: "scrb-admin", action: "read", resource: "Entity:ENT014602", query: "workbench/dossier" },
      { ts: "2026-07-02 10:11:41", actor: "sr", role: "scrb-admin", action: "read", resource: "Incident:INC010002", query: "workbench/case" },
      { ts: "2026-07-02 10:10:19", actor: "an1", role: "analyst", action: "read", resource: "Search", query: "KA68MC3164" },
      { ts: "2026-07-02 10:08:55", actor: "sp-bnu", role: "district", action: "read", resource: "Incidents", query: "governed/incidents" },
    ],
  },
} as const
