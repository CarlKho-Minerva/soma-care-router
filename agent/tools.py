"""MongoDB MCP tools for the Care Router agent."""

import json
import os
from google.adk.tools import FunctionTool
from pymongo import MongoClient

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI", "")
        _client = MongoClient(uri)
        _db = _client[os.environ.get("MONGODB_DB", "soma_care_router")]
    return _db


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
        conditions: Comma-separated relevant conditions (e.g., "elevated A1C, type 2 diabetes risk").
        current_medications: Comma-separated current medications to check for conflicts.
        max_results: Maximum number of providers to return.

    Returns:
        JSON string of matching providers with details.
    """
    db = _get_db()
    providers = db["providers"]

    query_text = f"{specialty} {conditions}".strip()

    # Try vector search first, fall back to text search
    try:
        pipeline = [
            {
                "$search": {
                    "index": "provider_search",
                    "text": {
                        "query": query_text,
                        "path": ["specialty", "subspecialties", "conditions_treated", "description"],
                    },
                }
            },
            {"$match": {"location.city": {"$regex": location_city, "$options": "i"}}},
            {"$limit": max_results},
            {
                "$project": {
                    "_id": 0,
                    "name": 1,
                    "specialty": 1,
                    "subspecialties": 1,
                    "clinic": 1,
                    "location": 1,
                    "rating": 1,
                    "review_count": 1,
                    "next_available": 1,
                    "accepts_insurance": 1,
                    "common_prescriptions": 1,
                    "conditions_treated": 1,
                    "languages": 1,
                    "description": 1,
                }
            },
        ]
        results = list(providers.aggregate(pipeline))
    except Exception:
        # Fallback: simple query
        results = list(
            providers.find(
                {
                    "specialty": {"$regex": specialty, "$options": "i"},
                    "location.city": {"$regex": location_city, "$options": "i"},
                },
                {"_id": 0},
            ).limit(max_results)
        )

    if not results:
        return json.dumps({"providers": [], "message": f"No {specialty} providers found in {location_city}."})

    # Check medication conflicts
    if current_medications:
        med_list = [m.strip().lower() for m in current_medications.split(",")]
        for provider in results:
            conflicts = []
            for rx in provider.get("common_prescriptions", []):
                rx_lower = rx.get("name", "").lower()
                for med in med_list:
                    if rx.get("conflicts_with") and med in [c.lower() for c in rx.get("conflicts_with", [])]:
                        conflicts.append(f"{rx['name']} may conflict with {med}")
            provider["medication_flags"] = conflicts if conflicts else ["No conflicts detected"]

    return json.dumps({"providers": results, "count": len(results)}, default=str)


def check_drug_interactions(
    current_medications: str,
    proposed_medication: str,
) -> str:
    """Check for known drug interactions between current and proposed medications.

    Args:
        current_medications: Comma-separated list of current medications.
        proposed_medication: The medication being considered.

    Returns:
        JSON string with interaction details.
    """
    db = _get_db()
    interactions_col = db["drug_interactions"]

    med_list = [m.strip().lower() for m in current_medications.split(",")]
    results = []

    for med in med_list:
        interaction = interactions_col.find_one(
            {
                "$or": [
                    {"drug_a": {"$regex": med, "$options": "i"}, "drug_b": {"$regex": proposed_medication, "$options": "i"}},
                    {"drug_a": {"$regex": proposed_medication, "$options": "i"}, "drug_b": {"$regex": med, "$options": "i"}},
                ]
            },
            {"_id": 0},
        )
        if interaction:
            results.append(interaction)

    if not results:
        return json.dumps({
            "interactions": [],
            "message": f"No known interactions found between {proposed_medication} and [{current_medications}].",
        })

    return json.dumps({"interactions": results, "count": len(results)}, default=str)


def get_provider_details(provider_name: str) -> str:
    """Get full details for a specific provider.

    Args:
        provider_name: Name of the provider to look up.

    Returns:
        JSON string with full provider details.
    """
    db = _get_db()
    provider = db["providers"].find_one(
        {"name": {"$regex": provider_name, "$options": "i"}},
        {"_id": 0},
    )
    if not provider:
        return json.dumps({"error": f"Provider '{provider_name}' not found."})
    return json.dumps(provider, default=str)


# Export as ADK FunctionTools
search_providers_tool = FunctionTool(func=search_providers)
check_drug_interactions_tool = FunctionTool(func=check_drug_interactions)
get_provider_details_tool = FunctionTool(func=get_provider_details)
