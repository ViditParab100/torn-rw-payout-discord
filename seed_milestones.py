"""
One-time script to seed chain history and faction upgrade milestones into MongoDB.
Run once after deployment:  python seed_milestones.py

Requires TORN_API_KEY and MONGO_URI in environment.
"""

import os
import milestone_detector

api_key = os.environ.get("TORN_API_KEY")
if not api_key:
    raise SystemExit("Set TORN_API_KEY in your environment before running this script.")

print("=== Seeding chain history milestones ===")
milestone_detector.detect_chain_milestones(api_key)

print("\n=== Seeding faction upgrade milestones ===")
milestone_detector.detect_upgrade_milestones(api_key)

print("\nDone. Check MongoDB milestones collection.")
