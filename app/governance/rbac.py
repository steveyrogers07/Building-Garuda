"""GARUDA - role-based access control (Phase 9 governance).

Roles map to jurisdiction scopes; every read is filtered to what the principal may
see, and privileged actions are gated. In production the principal comes from the
Catalyst Web SDK / API Gateway; locally it is supplied via headers (X-Role/X-Scope).

Roles: scrb-admin (state) · district (one district) · station (one station) ·
analyst (read-all, PII-masked) · case-officer (assigned cases) · ethics (audit /
fairness / model cards only - no case PII).
"""
from __future__ import annotations

ROLES = {"scrb-admin", "district", "station", "analyst", "case-officer", "ethics"}

# (role, action, resource) tuples that are explicitly denied.
_DENY = {
    ("ethics", "read", "incident_pii"),
    ("analyst", "write", "canonical"),
    ("district", "write", "canonical"),
    ("station", "write", "canonical"),
}


class Principal:
    def __init__(self, actor="anonymous", role="analyst", scope=None, ip=""):
        self.actor, self.role, self.scope, self.ip = actor, (role or "analyst"), scope, ip

    def __repr__(self):
        return f"Principal({self.actor},{self.role}:{self.scope})"


def authorize(principal, action, resource):
    """Raise PermissionError if the principal may not perform action on resource."""
    if principal.role not in ROLES:
        raise PermissionError(f"unknown role: {principal.role}")
    if (principal.role, action, resource) in _DENY:
        raise PermissionError(f"{principal.role} may not {action} {resource}")
    if action == "write" and resource == "canonical" and principal.role != "scrb-admin":
        raise PermissionError("canonical writes require scrb-admin + human approval")
    return True


def in_scope(principal, district=None, station=None):
    """May this principal see a record in the given district/station?"""
    r = principal.role
    if r in ("scrb-admin", "analyst", "case-officer"):
        return True
    if r == "district":
        return principal.scope == district
    if r == "station":
        return principal.scope == station
    return False                              # ethics → no case rows


def jurisdiction_filter(rows, principal, district_key="district_code", station_key="station_code"):
    """Filter a list of incident-like rows to the principal's jurisdiction."""
    if principal.role in ("scrb-admin", "analyst"):
        return rows
    if principal.role == "district":
        return [r for r in rows if r.get(district_key) == principal.scope]
    if principal.role == "station":
        return [r for r in rows if r.get(station_key) == principal.scope]
    return []                                 # ethics / unknown → none
