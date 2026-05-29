"""Seed MongoDB Atlas with provider and drug interaction data."""

import json
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()


def main():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        print("Error: MONGODB_URI not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    db_name = os.environ.get("MONGODB_DB", "soma_care_router")
    client = MongoClient(uri)
    db = client[db_name]

    data_dir = os.path.dirname(__file__)

    # Seed providers
    with open(os.path.join(data_dir, "providers.json")) as f:
        providers = json.load(f)

    db["providers"].drop()
    if providers:
        db["providers"].insert_many(providers)
        print(f"✅ Inserted {len(providers)} providers")

    # Seed drug interactions
    with open(os.path.join(data_dir, "drug_interactions.json")) as f:
        interactions = json.load(f)

    db["drug_interactions"].drop()
    if interactions:
        db["drug_interactions"].insert_many(interactions)
        print(f"✅ Inserted {len(interactions)} drug interactions")

    # Create text search index on providers
    try:
        db["providers"].create_index(
            [
                ("specialty", "text"),
                ("subspecialties", "text"),
                ("conditions_treated", "text"),
                ("description", "text"),
            ],
            name="provider_text_search",
        )
        print("✅ Created text search index on providers")
    except Exception as e:
        print(f"⚠️  Index creation note: {e}")

    print(f"\n🩺 Database '{db_name}' seeded successfully!")
    print(f"   Collections: {db.list_collection_names()}")

    client.close()


if __name__ == "__main__":
    main()
