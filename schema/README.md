# schema/ — Catalyst Data Store definitions (Phase 2)

Canonical table definitions and seed/import scripts for the **Catalyst Data Store**. Everything downstream reads this canonical schema (never the raw source format).

## Canonical tables
- `Incidents` — IncidentID, FIR_No, Date_Time, Lat, Long, District_Code, Station_Code, Crime_Type, **IPC_BNS_Code**, MO_Cluster_ID, Series_ID, Source_FIR_URL, Confidence, Status, Created_By
- `Entities` — EntityID, **Canonical_ID**, Type(Person/Vehicle/Phone), Value, Alias_Of, Match_Confidence
- `Incident_Edges` — IncidentID, EntityID, Role, Edge_Weight, Evidence_Type
- `Predictive_Risk` — Grid_ID, Time_Shift, Crime_Type, Risk_Probability, Model_Version, Backtest_PAI
- `MO_Clusters` · `Crime_Series` · `Socioeconomic` · `Geo_Boundaries` · `Alerts` · `Review_Queue` · `Audit_Log`

> Catalyst auto-adds `ROWID, CREATORID, CREATEDTIME, MODIFIEDTIME` to every table. Full contract (required/optional/fallback per field) is in [../docs/GARUDA_DATA_READINESS.md](../docs/GARUDA_DATA_READINESS.md).
