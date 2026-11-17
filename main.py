"""Forecast GTA VI's launch-day Twitch viewers, hours 2-24, as five quantiles.

Method (validated on the kit's four practice launches, see README):
  A launch day on Twitch is driven by rolling midnight-local unlocks: the
  UK unlocks at 00:00 UTC, the US east coast at 05:00 UTC, the west coast at
  08:00 UTC, so the audience is small in the first hour, dips, then climbs
  steeply into the US evening.  A flat persistence forecast misses that
  shape entirely.

  This program therefore learns the shape from the case's own comparables:
  it keeps only past launches whose unlock was a rolling midnight local
  (console launches like GTA VI, no simultaneous global unlock, no early
  access), and for each hour h measures, over those launches, the log ratio
  ln(viewers_h / viewers_1) of that hour's count to the launch's hour-1
  count.  The forecast for hour h is hour 1's print times exp(median ratio),
  with a log spread equal to the cross-launch standard deviation of the
  ratio (x1.05, tuned on practice), giving honest 5/25/50/75/95% quantiles
  on the log scale the contest scores.

  Everything is computed from the case file at run time: no hard-coded
  curve, no network, no model call.  Output is deterministic.

Run:  MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import statistics
import sys
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# The grader's -P leaves /bot off sys.path; nothing beside main.py is needed.
INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
FIRST_HOUR = 1
LAST_HOUR = 24
# How many launches must carry an hour's ratio before it is trusted.
MIN_LAUNCHES = 3
# Spread multiplier, chosen on the practice cases (0.9-1.2 all score within
# 0.005 of each other; 1.05 also brings 90% coverage nearest to 0.9).
SPREAD_SCALE = 1.05
# Floor on the log spread so a freakishly agreeing trio cannot claim certainty.
MIN_SPREAD = 0.05
# Fallback spread growth for hours with too few launches (house baseline's).
FALLBACK_SIGMA = 0.15


def parse_time(text):
    """ISO-8601 timestamp (with Z or an offset) to an aware datetime."""
    return datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def round_half_up_2dp(value):
    """Round to 2 decimals, halves up; whole numbers come back as ints."""
    rounded = Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    as_float = float(rounded)
    return int(as_float) if as_float.is_integer() else as_float


def release_day_curve(comparable):
    """{hour: viewers} for a comparable's release UTC day, hours 1-24.

    Only hours with a positive count are kept; a sparse source simply
    leaves the missing hours out.
    """
    day_start = parse_time(comparable["day_start"])
    curve = {}
    for point in comparable.get("hourly") or []:
        viewers = point.get("viewers")
        if not isinstance(viewers, (int, float)) or viewers <= 0:
            continue
        try:
            hour = int((parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        except (KeyError, TypeError, ValueError):
            continue
        if FIRST_HOUR <= hour <= LAST_HOUR:
            curve[hour] = float(viewers)
    return curve


def unlock_is_rolling_midnight(comparable):
    """True for a console launch that unlocked at midnight local, rolling.

    The case's comparables carry a free-text unlock note ending in a Tier
    tag.  GTA VI itself is a console-only, rolling-midnight, single-player
    launch with no early access; the closest analogues share that shape.
    Simultaneous global unlocks (one worldwide hour) and early-access
    launches have a different day curve and are left out.
    """
    note = str(comparable.get("unlock", "")).lower()
    if "tier: comparable" not in note:
        return False
    if "midnight local" not in note:
        return False
    if "single global" in note or "simultaneous" in note:
        return False
    return True


def is_target_history(comparable):
    """True for the target game's own pre-release category history.

    It is not a launch at all (its day_start is the premiere date, not a
    release day), so its "release-day curve" would be the premiere day's
    sparse points.  It must never enter training, at any fallback level.
    """
    note = str(comparable.get("unlock", "")).lower()
    return "tier: target-history" in note or "not a launch" in note


def pick_training_curves(comparables):
    """Release-day curves to learn the shape from, best set first.

    Prefer rolling-midnight launches; if fewer than three carry a usable
    curve, widen to every comparable-tier launch; if still too few, use
    every comparable with a curve at all.  The caller falls back to a
    flat forecast when even that is empty.
    """
    curves = [(c, release_day_curve(c)) for c in comparables or []
              if not is_target_history(c)]
    # A usable curve starts at hour 1, covers most of the day, and reaches
    # the late hours: a truncated release day would skew the evening shape.
    usable = [(c, d) for c, d in curves
              if FIRST_HOUR in d and len(d) >= 12
              and any(h >= 13 for h in d)]
    rolling = [d for c, d in usable if unlock_is_rolling_midnight(c)]
    if len(rolling) >= MIN_LAUNCHES:
        return rolling
    tiered = [d for c, d in usable if "tier: comparable" in str(c.get("unlock", "")).lower()]
    if len(tiered) >= MIN_LAUNCHES:
        return tiered
    return [d for _, d in usable]


def log_ratios_by_hour(curves):
    """{hour: [ln(v_h / v_1)]} over the training curves that carry both hours."""
    ratios = {h: [] for h in range(FIRST_HOUR + 1, LAST_HOUR + 1)}
    for curve in curves:
        first = curve.get(FIRST_HOUR)
        if not first:
            continue
        for hour in range(FIRST_HOUR + 1, LAST_HOUR + 1):
            value = curve.get(hour)
            if value:
                ratios[hour].append(math.log(value / first))
    return ratios


def flat_quantiles(print_1, hour):
    """House-style persistence quantiles: the fallback for thin hours."""
    return [
        round_half_up_2dp(print_1 * math.exp(z * FALLBACK_SIGMA * math.sqrt(hour - 1)))
        for z in Z
    ]


def shape_quantiles(print_1, hour, ratios):
    """Median-shape quantiles for one hour, or the flat fallback."""
    values = ratios.get(hour) or []
    if len(values) < MIN_LAUNCHES:
        return flat_quantiles(print_1, hour)
    centre = statistics.median(values)
    spread = max(MIN_SPREAD, statistics.pstdev(values) * SPREAD_SCALE)
    quantiles = []
    for z in Z:
        q = print_1 * math.exp(centre + z * spread)
        q = min(max(q, 0.01), 1_000_000_000)
        quantiles.append(round_half_up_2dp(q))
    # Rounding can only move a value by a cent; keep the row non-decreasing.
    for i in range(1, len(quantiles)):
        if quantiles[i] < quantiles[i - 1]:
            quantiles[i] = quantiles[i - 1]
    return quantiles


def hour_one_print(case):
    """Hour 1's print, with graceful fallbacks so output is always valid."""
    for row in case.get("known") or []:
        if row.get("hour") == FIRST_HOUR and isinstance(row.get("viewers"), (int, float)):
            return max(1.0, float(row["viewers"]))
    hourly = case.get("history_hourly") or []
    if hourly:
        last = hourly[-1].get("viewers")
        if isinstance(last, (int, float)) and last > 0:
            return float(last)
    return 1.0


def forecast_case(case):
    """The 23-row forecast object for one case."""
    print_1 = hour_one_print(case)
    ratios = log_ratios_by_hour(pick_training_curves(case.get("comparables")))
    hours = []
    for row in case.get("forecast") or []:
        hour = row.get("hour")
        if not isinstance(hour, int) or not FIRST_HOUR < hour <= LAST_HOUR:
            continue
        hours.append({"hour": hour, "q": shape_quantiles(print_1, hour, ratios)})
    # A case that lists no forecast rows still gets a full, valid output.
    seen = {row["hour"] for row in hours}
    for hour in range(FIRST_HOUR + 1, LAST_HOUR + 1):
        if hour not in seen:
            hours.append({"hour": hour, "q": shape_quantiles(print_1, hour, ratios)})
    hours.sort(key=lambda row: row["hour"])
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            forecast = forecast_case(case)
        except Exception:
            # Never leave a case without output: a flat forecast at 1 viewer
            # is valid and scores as the hour-1 fallback, far better than a crash.
            forecast = {"hours": [{"hour": h, "q": flat_quantiles(1.0, h)} for h in range(2, 25)]}
        out_path = OUTPUT_DIR / f"{path.stem}.out"
        out_path.write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
