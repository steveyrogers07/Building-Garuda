"""GARUDA - Qwen (QuickML LLM serving) FIR extractor; used when EXTRACTOR=qwen.

Schema-constrained extraction for messy/handwritten real FIRs. Falls back to the
rule-based extractor on ANY error so ingestion never hard-fails (and so dev/offline runs
work without spending QuickML credits).

Needs AppSail env_variables: QUICKML_ENDPOINT, QUICKML_TOKEN (OAuth scope
'QuickML.deployment.READ'). The QuickML RAG/LLM-serving API is POST-only; confirm the
exact request/response field names against your deployment's "View API" page.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from engines.extraction.rules import extract_fir as _rules_extract

# ingestion/ sits three levels up locally (repo_root/app/engines/extraction/);
# in a deployed AppSail bundle (app/ becomes the root) it would be two levels
# up instead - try both, same reasoning as shared/store.py and shared/refs.py.
_HERE = Path(__file__).resolve()
for _candidate in (_HERE.parents[3], _HERE.parents[2]):
    if (_candidate / "ingestion").is_dir():
        PROMPT_PATH = _candidate / "ingestion" / "extraction" / "prompt.md"
        break
else:
    PROMPT_PATH = _HERE.parents[3] / "ingestion" / "extraction" / "prompt.md"


def _build_prompt(text):
    tmpl = PROMPT_PATH.read_text(encoding="utf-8") if PROMPT_PATH.exists() else "{{OCR_TEXT}}"
    return tmpl.replace("{{OCR_TEXT}}", text)


def _call_quickml(prompt):
    endpoint = os.environ["QUICKML_ENDPOINT"]
    token = os.environ["QUICKML_TOKEN"]
    payload = json.dumps({"input": prompt, "max_tokens": 1024, "temperature": 0}).encode()
    req = urllib.request.Request(
        endpoint, data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Zoho-oauthtoken {token}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode())
    # confirm the exact output field against the QuickML deployment API contract
    return body.get("output") or body.get("text") or body.get("response") or json.dumps(body)


def _parse_json(s):
    m = re.search(r"\{.*\}", s.strip(), re.S)   # strip prose / code fences
    return json.loads(m.group(0) if m else s)


def extract_fir_qwen(text):
    try:
        rec = _parse_json(_call_quickml(_build_prompt(text)))
        rec.setdefault("persons", [])
        rec.setdefault("vehicles", [])
        rec.setdefault("phones", [])
        prov = {k: "llm" for k, v in rec.items() if v not in (None, "", [])}
        return rec, prov
    except Exception:
        return _rules_extract(text)   # graceful degradation
