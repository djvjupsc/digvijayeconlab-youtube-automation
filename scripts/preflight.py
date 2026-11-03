import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "content_plan.json"

def main():
    if not CONFIG.exists():
        raise SystemExit("ERROR: config/content_plan.json is missing.")

    with CONFIG.open("r", encoding="utf-8") as f:
        plan = json.load(f)

    required = ["brand", "language", "timezone", "audience", "content_pillars", "publishing"]
    missing = [key for key in required if key not in plan]
    if missing:
        raise SystemExit("ERROR: missing configuration keys: " + ", ".join(missing))

    if plan["brand"] != "DigvijayEconLab":
        raise SystemExit("ERROR: unexpected brand value.")

    publishing = plan["publishing"]
    if publishing.get("enabled") is not False:
        raise SystemExit("ERROR: publishing must remain disabled during setup.")
    if publishing.get("require_human_approval") is not True:
        raise SystemExit("ERROR: human approval must remain enabled during setup.")

    print("Preflight passed.")
    print(f"Brand: {plan['brand']}")
    print(f"Timezone: {plan['timezone']}")
    print(f"Content pillars: {len(plan['content_pillars'])}")
    print("Publishing: DISABLED (safe setup mode)")

if __name__ == "__main__":
    main()
