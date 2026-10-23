#!/usr/bin/env python3
# Usage: TOKEN_DIR=... python scripts/garmin_capability_probe.py <out_dir> [YYYY-MM-DD]
# Raw responses are personal health data: keep <out_dir> outside the repo.
"""Which Garmin Connect endpoints return data for this account? Read-only.

Uses the saved tokens in TOKEN_DIR (no password). For a recent day, calls every
data method of garminconnect 0.3.7, saves each raw response to OUT_DIR and
prints one line per method: data / empty / error, size and top-level keys.
"""
import json, os, sys, time
from datetime import date, timedelta
from garminconnect import Garmin

OUT_DIR = sys.argv[1]
DAY = sys.argv[2] if len(sys.argv) > 2 else (date.today() - timedelta(days=1)).isoformat()
WEEK_AGO = (date.fromisoformat(DAY) - timedelta(days=6)).isoformat()
os.makedirs(OUT_DIR, exist_ok=True)

g = Garmin()
g.login(os.path.expanduser(os.getenv("TOKEN_DIR", "~/.garminconnect")))

acts = g.get_activities_by_date((date.fromisoformat(DAY) - timedelta(days=30)).isoformat(), DAY) or []
act = acts[0]["activityId"] if acts else None
outdoor = next((a["activityId"] for a in acts if a.get("hasPolyline")), act)
strength = next((a["activityId"] for a in acts if (a.get("activityType") or {}).get("typeKey") == "strength_training"), None)
profile = g.get_user_profile() or {}
profile_pk = str(profile.get("id") or profile.get("userProfileNumber") or "")
devices = g.get_devices() or []
device_id = str(devices[0].get("deviceId")) if devices else None

calls = {
    # already used by upstream (to see what it drops)
    "get_stats": (DAY,), "get_sleep_data": (DAY,), "get_hrv_data": (DAY,), "get_stress_data": (DAY,),
    "get_heart_rates": (DAY,), "get_respiration_data": (DAY,), "get_steps_data": (DAY,),
    "get_training_readiness": (DAY,), "get_training_status": (DAY,), "get_max_metrics": (DAY,),
    "get_fitnessage_data": (DAY,), "get_endurance_score": (WEEK_AGO, DAY), "get_hill_score": (WEEK_AGO, DAY),
    "get_race_predictions": (), "get_weigh_ins": ((date.fromisoformat(DAY) - timedelta(days=90)).isoformat(), DAY),
    "get_blood_pressure": (WEEK_AGO, DAY), "get_hydration_data": (DAY,), "get_lifestyle_logging_data": (DAY,),
    # not used by upstream
    "get_spo2_data": (DAY,), "get_body_battery_events": (DAY,), "get_body_battery": (WEEK_AGO, DAY),
    "get_all_day_events": (DAY,), "get_floors": (DAY,), "get_intensity_minutes_data": (DAY,),
    "get_rhr_day": (DAY,), "get_daily_steps": (WEEK_AGO, DAY), "get_weekly_stress": (DAY, 4),
    "get_weekly_intensity_minutes": (WEEK_AGO, DAY), "get_running_tolerance": (WEEK_AGO, DAY),
    "get_nutrition_daily_food_log": (DAY,), "get_nutrition_daily_meals": (DAY,),
    "get_heart_rate_zones": (), "get_user_profile": (), "get_userprofile_settings": (), "get_devices": (),
    "get_primary_training_device": (), "get_device_alarms": (), "get_personal_record": (), "get_goals": (),
    "get_earned_badges": (), "get_in_progress_badges": (), "get_workouts": (), "get_training_plans": (),
    "get_golf_summary": (), "get_activity_types": (), "get_unit_system": (),
    "get_menstrual_data_for_date": (DAY,),
}
if act:
    calls.update({"get_activity": (act,), "get_activity_details": (act,), "get_activity_splits": (act,),
                  "get_activity_split_summaries": (act,), "get_activity_typed_splits": (act,),
                  "get_activity_gear": (act,), "get_activity_hr_in_timezones": (act,),
                  "get_activity_weather": (outdoor,)})
if strength:
    calls["get_activity_exercise_sets"] = (strength,)
if profile_pk:
    calls.update({"get_gear": (profile_pk,), "get_gear_defaults": (profile_pk,)})
if device_id:
    calls["get_device_settings"] = (device_id,)


def summarize(data):
    if data in (None, {}, [], ""):
        return "empty", 0, ""
    text = json.dumps(data, default=str)
    keys = list(data)[:12] if isinstance(data, dict) else (list(data[0])[:12] if data and isinstance(data[0], dict) else [])
    return "data", len(text), ",".join(map(str, keys))


print(f"day={DAY} activities_30d={len(acts)} activity={act} outdoor={outdoor} strength={strength} devices={len(devices)}")
for name, args in calls.items():
    try:
        data = getattr(g, name)(*args)
        status, size, keys = summarize(data)
        with open(os.path.join(OUT_DIR, f"{name}.json"), "w") as f:
            json.dump(data, f, default=str, indent=1)
    except Exception as err:
        status, size, keys = "error", 0, f"{type(err).__name__}: {str(err)[:80]}"
    print(f"{name:34} {status:6} {size:>8}  {keys}")
    time.sleep(1)
