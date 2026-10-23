"""Keep every raw Garmin Connect response in SurrealDB (garmin-surreal).

Upstream turns a few fields of each Garmin response into points and drops the
rest. With "raw" in FETCH_SELECTION, every data call also stores the whole
response, one record per call, so nothing Garmin returns is lost and more
fields can be read out later with SurrealQL. With "extras", the fetcher also
calls the endpoints upstream never uses (SpO2, floors, Body Battery events,
full activity details and weather, profile, devices, personal records, ...).

Table per method: raw_<method>, record ID = the call's arguments, e.g.
raw_get_sleep_data:['2026-10-22'] or raw_get_activity_weather:['24816165305'].
Account snapshots (profile, devices, ...) are kept once per UTC day, with the
day as the last ID part: raw_get_devices:['2026-10-23'].
"""

import logging
import os
from datetime import datetime, timezone

from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

try:
    from . import surreal_store
except ImportError:
    import surreal_store

# Not JSON data, or polled every few minutes (its fields are already stored as DeviceSync).
NOT_MIRRORED = {"download_activity", "get_full_name", "get_unit_system",
                "get_device_last_used", "get_last_activity"}

# Per day: endpoints upstream does not call.
EXTRA_DAILY = (
    ("get_spo2_data", lambda d: (d,)),
    ("get_body_battery_events", lambda d: (d,)),
    ("get_body_battery", lambda d: (d, d)),
    ("get_all_day_events", lambda d: (d,)),
    ("get_floors", lambda d: (d,)),
    ("get_intensity_minutes_data", lambda d: (d,)),
    ("get_rhr_day", lambda d: (d,)),
    ("get_nutrition_daily_food_log", lambda d: (d,)),
    ("get_nutrition_daily_meals", lambda d: (d,)),
)

# Per activity of the day (upstream already fetches the list and HR zones).
EXTRA_ACTIVITY = (
    "get_activity",
    "get_activity_details",
    "get_activity_weather",
    "get_activity_splits",
    "get_activity_split_summaries",
    "get_activity_typed_splits",
    "get_activity_gear",
)

# Account snapshots, once per UTC day.
EXTRA_SNAPSHOT = (
    ("get_user_profile", ()),
    ("get_userprofile_settings", ()),
    ("get_devices", ()),
    ("get_primary_training_device", ()),
    ("get_heart_rate_zones", ()),
    ("get_personal_record", ()),
    ("get_earned_badges", ()),
    ("get_in_progress_badges", ()),
    ("get_goals", ("active",)),
    ("get_goals", ("future",)),
    ("get_goals", ("past",)),
    ("get_training_plans", ()),
)
WORKOUTS_PAGE = 100

_snapshot_day = None     # UTC day of the last account snapshot
_snapshot_tag = None     # set while taking a snapshot: appended to every key
_activity_ids = {}       # date_str -> activity ids seen in get_activities_by_date
_pending_error = None    # first raw-write failure since the last raise_pending()


def _selected(flag):
    return flag in os.getenv("FETCH_SELECTION", "")


def _today():
    return datetime.now(timezone.utc).date().isoformat()


def _key(method, args, kwargs):
    if method == "connectapi":
        key = [str(args[0]) if args else str(kwargs.get("path", ""))]
        key += [f"{k}={kwargs[k]}" for k in sorted(kwargs) if k not in ("path", "method")]
    else:
        key = [a if isinstance(a, str) else str(a) for a in args]
        key += [f"{k}={kwargs[k]}" for k in sorted(kwargs)]
    if _snapshot_tag:
        return key + [_snapshot_tag]
    return key or [_today()]


class MirroredGarmin:
    """Wraps a Garmin client; every data call's response is also stored raw.

    A failed raw write never raises here: upstream wraps several Garmin calls in
    broad try/except blocks that would swallow it and mark the date as done.
    The error is kept and raised by raise_pending() at the end of the date.
    """

    def __init__(self, garmin):
        object.__setattr__(self, "_garmin", garmin)

    def __getattr__(self, name):
        attr = getattr(self._garmin, name)
        if not callable(attr) or name in NOT_MIRRORED or not (name.startswith("get_") or name == "connectapi"):
            return attr

        def call(*args, **kwargs):
            global _pending_error
            result = attr(*args, **kwargs)
            if name == "connectapi" and str(kwargs.get("method", "GET")).upper() != "GET":
                return result
            if name == "get_activities_by_date" and args and isinstance(result, list):
                _activity_ids[str(args[0])] = [a.get("activityId") for a in result if a.get("activityId")]
            if _pending_error is None:  # after one failure, skip writes: the date is redone anyway
                try:
                    surreal_store.write_raw(name, _key(name, args, kwargs), result)
                except surreal_store.SurrealStoreError as err:
                    logging.error(f"Raw write failed for {name}{args}: {err}")
                    _pending_error = err
            return result
        return call

    def __setattr__(self, name, value):
        setattr(self._garmin, name, value)


def mirror(garmin):
    """Return the client wrapped for raw storage when "raw" is in FETCH_SELECTION."""
    if not _selected("raw") or isinstance(garmin, MirroredGarmin):
        return garmin
    logging.info("Raw mirror on : every Garmin response is also stored in raw_* tables")
    return MirroredGarmin(garmin)


def raise_pending():
    """Raise a raw-write failure from this date, so fetch_write_bulk retries the date."""
    global _pending_error
    err, _pending_error = _pending_error, None
    if err is not None:
        raise surreal_store.SurrealStoreError(f"Raw write failed earlier in this date: {err}") from err


def _try(garmin, method, *args):
    """Call one extra endpoint; a feature this account lacks is skipped, not an error."""
    try:
        return getattr(garmin, method)(*args)
    except (GarminConnectTooManyRequestsError, GarminConnectAuthenticationError):
        raise  # upstream waits (429) or logs in again, then retries the date
    except Exception as err:
        logging.warning(f"Skipped : {method}{args} — {type(err).__name__}: {str(err)[:120]}")
        return None


def _snapshot(garmin):
    """Account-level data, once per UTC day, each record keyed with the day."""
    global _snapshot_tag
    _snapshot_tag = _today()
    try:
        results = {}
        for method, args in EXTRA_SNAPSHOT:
            results[method] = _try(garmin, method, *args)
        for device in results.get("get_devices") or []:
            if device.get("deviceId"):
                _try(garmin, "get_device_settings", str(device["deviceId"]))
        profile_id = (results.get("get_user_profile") or {}).get("id")
        if profile_id:
            _try(garmin, "get_gear", str(profile_id))
        start = 0
        while True:  # all saved workouts, page by page
            page = _try(garmin, "get_workouts", start, WORKOUTS_PAGE)
            if not isinstance(page, list) or len(page) < WORKOUTS_PAGE:
                break
            start += WORKOUTS_PAGE
    finally:
        _snapshot_tag = None


def fetch_extras(garmin, date_str):
    """Call the endpoints upstream never uses for one day ("extras" in FETCH_SELECTION).

    Needs the mirrored client: the responses are stored by the mirror itself.
    """
    global _snapshot_day
    if not isinstance(garmin, MirroredGarmin):
        logging.warning("Skipped : extras need 'raw' in FETCH_SELECTION to be stored")
        return
    for method, args in EXTRA_DAILY:
        _try(garmin, method, *args(date_str))
    activity_ids = _activity_ids.pop(date_str, None)
    if activity_ids is None:
        activities = _try(garmin, "get_activities_by_date", date_str, date_str) or []
        activity_ids = [a.get("activityId") for a in activities if a.get("activityId")]
        _activity_ids.pop(date_str, None)
    for activity_id in activity_ids:
        for method in EXTRA_ACTIVITY:
            _try(garmin, method, str(activity_id))
    if _snapshot_day != _today():
        _snapshot(garmin)
        _snapshot_day = _today()
    logging.info(f"Success : Fetched extra Garmin endpoints for date {date_str} ({len(activity_ids)} activities)")
