"""Monthly cost of buying vs renting a GPU (episode 1).

Buy: (card + new PSU, if needed) / months + energy. Energy counts the PC switched on `hours_on_per_month` (idle PC +
idle GPU) plus the extra the GPU draws during `hours_used_per_month`.
Rent on demand: (hours used + setup time of each session) x price per hour x exchange rate.
Rent always on: hours on x price per hour x exchange rate.
Break-even: hours of use per month from which buying is cheaper than renting on demand.

Prices come from `prices.csv`, filled in by hand with the source and date of each value. Rows without a price are
rejected.
"""
import csv
from pathlib import Path

ASSUMPTIONS = ["brl_per_usd", "brl_per_kwh", "hours_used_per_month", "hours_on_per_month", "pc_idle_watts", "months",
               "sessions_per_month", "setup_minutes_per_session", "new_psu_price_brl"]
COLUMNS = ["id", "name", "option", "brl_per_month", "break_even_hours_per_month", "data_status"]
YES = {"yes", "y", "true", "1"}


class CostError(Exception):
    pass


def _num(v):
    v = (v or "").strip().replace(",", ".")
    return float(v) if v else None


def read_assumptions(path):
    with open(path, encoding="utf-8") as f:
        rows = {r["key"]: r for r in csv.DictReader(f)}
    missing = [k for k in ASSUMPTIONS if k not in rows or _num(rows[k]["value"]) is None]
    if missing:
        raise CostError(f"{Path(path).name}: fill in {', '.join(missing)}")
    return {k: _num(rows[k]["value"]) for k in ASSUMPTIONS}


def read_prices(path):
    with open(path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("id", "").strip() and not r["id"].startswith("#")]
    missing = []
    for r in rows:
        if r["kind"] not in ("buy", "rent"):
            raise CostError(f"{r['id']}: kind {r['kind']!r} (use buy or rent)")
        key = "price_brl" if r["kind"] == "buy" else "price_usd_per_hour"
        if _num(r.get(key)) is None:
            missing.append(f"{r['id']} ({key})")
        if r["kind"] == "buy" and _num(r.get("load_watts")) is None:
            missing.append(f"{r['id']} (load_watts)")
    if missing:
        raise CostError(f"{Path(path).name}: missing values in {', '.join(missing)}")
    return rows


def buy_per_month(r, a, hours_used=None):
    hours_used = a["hours_used_per_month"] if hours_used is None else hours_used
    price = _num(r["price_brl"]) + (a["new_psu_price_brl"] if r.get("needs_new_psu", "").strip().lower() in YES else 0)
    idle = _num(r.get("idle_watts")) or 0
    load = _num(r["load_watts"])
    kwh = (a["hours_on_per_month"] * (a["pc_idle_watts"] + idle) + hours_used * max(load - idle, 0)) / 1000
    return price / a["months"] + kwh * a["brl_per_kwh"]


def rent_on_demand_per_month(r, a, hours_used=None):
    hours_used = a["hours_used_per_month"] if hours_used is None else hours_used
    hours = hours_used + a["sessions_per_month"] * a["setup_minutes_per_session"] / 60
    return hours * _num(r["price_usd_per_hour"]) * a["brl_per_usd"]


def rent_always_on_per_month(r, a):
    return a["hours_on_per_month"] * _num(r["price_usd_per_hour"]) * a["brl_per_usd"]


def break_even(buy, rent, a, ceiling=720):
    """Smallest whole number of hours of use per month where buying costs <= renting on demand (None if never)."""
    for h in range(0, ceiling + 1):
        if buy_per_month(buy, a, h) <= rent_on_demand_per_month(rent, a, h):
            return h
    return None


def calculate(prices, assumptions, reference=None):
    """cost.csv rows. `reference` = id of the rental used for the break-even (default: the cheapest one)."""
    rentals = [r for r in prices if r["kind"] == "rent"]
    ref = None
    if rentals:
        ref = next((r for r in rentals if r["id"] == reference), None) if reference else \
            min(rentals, key=lambda r: _num(r["price_usd_per_hour"]))
        if reference and ref is None:
            raise CostError(f"reference rental {reference!r} is not in prices.csv")
    out = []
    for r in prices:
        status = r.get("status", "").strip() or "?"
        if r["kind"] == "buy":
            be = break_even(r, ref, assumptions) if ref else None
            out.append({"id": r["id"], "name": r["name"], "option": "buy",
                        "brl_per_month": round(buy_per_month(r, assumptions), 2),
                        "break_even_hours_per_month": "" if be is None else be, "data_status": status})
        else:
            out.append({"id": r["id"], "name": r["name"], "option": "rent_on_demand",
                        "brl_per_month": round(rent_on_demand_per_month(r, assumptions), 2),
                        "break_even_hours_per_month": "", "data_status": status})
            out.append({"id": r["id"], "name": r["name"], "option": "rent_always_on",
                        "brl_per_month": round(rent_always_on_per_month(r, assumptions), 2),
                        "break_even_hours_per_month": "", "data_status": status})
    return out


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
