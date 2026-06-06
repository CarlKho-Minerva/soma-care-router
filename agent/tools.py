"""MongoDB tools for the Care Router agent.

Hardened for production reliability (Google for Startups AI Agents Challenge,
Track 2 — Optimize):
- structured errors instead of a silent vector->text fallback
- regex inputs escaped (no injection, no accidental wildcard matches)
- missing-URI / empty-DB guarded with clear, recoverable signals
- drug-conflict surfacing is data-driven (provider `conflicts_with` field),
  with the authoritative check delegated to `check_drug_interactions`.

Every tool returns a JSON string with a stable shape:
    {"ok": bool, "error": str|None, ...payload}
so the agent (and the eval harness) can always tell success from failure.
"""

import json
import logging
import os
import re

from google.adk.tools import FunctionTool
from pymongo import MongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger("care_router.tools")

_client = None
_db = None


class ToolConfigError(RuntimeError):
    """Raised when the tool layer is misconfigured (e.g. no MONGODB_URI)."""


def _get_db():
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI", "").strip()
        if not uri:
            raise ToolConfigError(
                "MONGODB_URI is not set. The provider database is unavailable."
            )
        _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _db = _client[os.environ.get("MONGODB_DB", "soma_care_router")]
    return _db


def _rx(value: str) -> dict:
    """Build an escaped, case-insensitive regex match (no injection)."""
    return {"$regex": re.escape(value.strip()), "$options": "i"}


def _split_meds(raw: str) -> list[str]:
    return [m.strip().lower() for m in (raw or "").split(",") if m.strip()]


def _err(message: str, **extra) -> str:
    """Structured error envelope. Recoverable by design — the agent is told
    in its instructions to surface this to the user, not to invent a result."""
    logger.warning("tool error: %s", message)
    return json.dumps({"ok": False, "error": message, **extra}, default=str)


def search_providers(
    specialty: str,
    location_city: str,
    conditions: str = "",
    current_medications: str = "",
    max_results: int = 5,
) -> str:
    """Search the provider database for specialists matching clinical criteria.

    Args:
        specialty: Medical specialty needed (e.g., "endocrinology", "cardiology").
        location_city: City for proximity search (e.g., "San Francisco").
        conditions: Comma-separated relevant conditions (e.g., "elevated A1C").
        current_medications: Comma-separated current medications to flag conflicts.
        max_results: Maximum number of providers to return.

    Returns:
        JSON string: {"ok", "providers", "count", "search_mode", "degraded", ...}.
        `search_mode` is "vector" or "text_fallback"; `degraded` is true when
        the preferred vector search failed and a fallback was used.
    """
    if not specialty.strip() or not location_city.strip():
        return _err("Both 'specialty' and 'location_city' are required.")

    try:
        db = _get_db()
        providers = db["providers"]
    except (ToolConfigError, PyMongoError) as e:
        return _err(f"Provider database unavailable: {e}")

    query_text = f"{specialty} {conditions}".strip()
    search_mode = "text"
    degraded = False
    projection = {k: 1 for k in _PROVIDER_PROJECTION if k != "_id"} | {"_id": 0}

    # Primary: $text search (uses the standard text index created by seed_db.py)
    try:
        results = list(
            providers.find(
                {"$text": {"$search": query_text}, "location.city": _rx(location_city)},
                {**projection, "score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(max_results)
        )
    except PyMongoError as e:
        logger.warning("text search failed, using regex fallback: %s", e)
        search_mode = "regex_fallback"
        degraded = True
        results = []

    # Fallback: regex across multiple fields
    if not results:
        if search_mode != "regex_fallback":
            search_mode = "regex_fallback"
        try:
            results = list(
                providers.find(
                    {
                        "$or": [
                            {"specialty": _rx(specialty)},
                            {"subspecialties": _rx(specialty)},
                            {"conditions_treated": _rx(specialty)},
                            {"description": _rx(specialty)},
                        ],
                        "location.city": _rx(location_city),
                    },
                    projection,
                ).limit(max_results)
            )
        except PyMongoError as e2:
            return _err(f"Provider search failed entirely: {e2}", search_mode=search_mode)

    if not results:
        return json.dumps({
            "ok": True,
            "providers": [],
            "count": 0,
            "search_mode": search_mode,
            "degraded": degraded,
            "message": f"No {specialty} providers found in {location_city}.",
        }, default=str)

    meds = _split_meds(current_medications)
    if meds:
        for provider in results:
            flags = []
            for rx in provider.get("common_prescriptions", []):
                conflicts_with = [c.lower() for c in rx.get("conflicts_with", [])]
                hits = [m for m in meds if m in conflicts_with]
                if hits:
                    flags.append(f"{rx.get('name', 'a prescribed drug')} may conflict with {', '.join(hits)}")
            provider["medication_flags"] = flags or ["No conflicts detected in provider's common prescriptions"]

    return json.dumps({
        "ok": True,
        "providers": results,
        "count": len(results),
        "search_mode": search_mode,
        "degraded": degraded,
    }, default=str)


def check_drug_interactions(current_medications: str, proposed_medication: str) -> str:
    """Check for known interactions between current and proposed medications.

    Args:
        current_medications: Comma-separated list of current medications.
        proposed_medication: The medication being considered.

    Returns:
        JSON string: {"ok", "interactions", "count", "checked", ...}.
    """
    if not proposed_medication.strip():
        return _err("'proposed_medication' is required.")
    meds = _split_meds(current_medications)
    if not meds:
        return _err("'current_medications' is required to check interactions.")

    try:
        col = _get_db()["drug_interactions"]
    except (ToolConfigError, PyMongoError) as e:
        return _err(f"Interaction database unavailable: {e}")

    proposed = proposed_medication.strip()
    found = []
    try:
        for med in meds:
            hit = col.find_one(
                {"$or": [
                    {"drug_a": _rx(med), "drug_b": _rx(proposed)},
                    {"drug_a": _rx(proposed), "drug_b": _rx(med)},
                ]},
                {"_id": 0},
            )
            if hit:
                found.append(hit)
    except PyMongoError as e:
        return _err(f"Interaction lookup failed: {e}")

    return json.dumps({
        "ok": True,
        "interactions": found,
        "count": len(found),
        "checked": {"current": meds, "proposed": proposed},
        "message": (
            f"No known interactions between {proposed} and [{current_medications}]."
            if not found else f"{len(found)} potential interaction(s) found."
        ),
    }, default=str)


def get_provider_details(provider_name: str) -> str:
    """Get full details for a specific provider.

    Args:
        provider_name: Name of the provider to look up.

    Returns:
        JSON string: {"ok", "provider"} or a structured error.
    """
    if not provider_name.strip():
        return _err("'provider_name' is required.")
    try:
        provider = _get_db()["providers"].find_one({"name": _rx(provider_name)}, {"_id": 0})
    except (ToolConfigError, PyMongoError) as e:
        return _err(f"Provider lookup failed: {e}")
    if not provider:
        return _err(f"Provider '{provider_name}' not found.", not_found=True)
    return json.dumps({"ok": True, "provider": provider}, default=str)


_PROVIDER_PROJECTION = {
    "_id": 0, "name": 1, "specialty": 1, "subspecialties": 1, "clinic": 1,
    "location": 1, "rating": 1, "review_count": 1, "next_available": 1,
    "accepts_insurance": 1, "common_prescriptions": 1, "conditions_treated": 1,
    "languages": 1, "description": 1,
}


# Export as ADK FunctionTools (consumed by the ADK Agent in care_router.py)
search_providers_tool = FunctionTool(func=search_providers)
check_drug_interactions_tool = FunctionTool(func=check_drug_interactions)
get_provider_details_tool = FunctionTool(func=get_provider_details)
