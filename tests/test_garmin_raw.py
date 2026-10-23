"""Raw mirror and extra endpoints, with a fake Garmin client and a real SurrealDB 3.x."""

import pytest
from garminconnect import GarminConnectConnectionError, GarminConnectTooManyRequestsError

import garmin_raw
import surreal_store


class FakeGarmin:
    display_name = "abc"

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("get_"):
            raise AttributeError(name)

        def method(*args, **kwargs):
            self.calls.append((name, args))
            if name == "get_activities_by_date":
                return [{"activityId": 111}, {"activityId": 222}]
            if name == "get_floors":
                raise GarminConnectConnectionError("404 not supported on this device")
            if name == "get_devices":
                return [{"deviceId": 9}]
            if name == "get_user_profile":
                return {"id": 77}
            return {"method": name, "args": list(args), "missing": None, "series": [[1, None, 3]]}
        return method

    def connectapi(self, path, **kwargs):
        self.calls.append(("connectapi", (path,)))
        return {"ok": True}

    def download_activity(self, activity_id, **kwargs):
        return b"FITDATA"


@pytest.fixture
def mirrored(store, monkeypatch):
    monkeypatch.setenv("FETCH_SELECTION", "daily_avg,activity,raw,extras")
    monkeypatch.setattr(garmin_raw, "_snapshot_day", None)
    monkeypatch.setattr(garmin_raw, "_pending_error", None)
    fake = FakeGarmin()
    return garmin_raw.mirror(fake), fake


def raw(table, key):
    rows = surreal_store._query("SELECT * FROM $id;", {"id": surreal_store.RecordID(table, key)})[0]
    return rows[0] if rows else None


def test_mirror_is_off_without_the_flag(monkeypatch):
    monkeypatch.setenv("FETCH_SELECTION", "daily_avg,sleep")
    fake = FakeGarmin()
    assert garmin_raw.mirror(fake) is fake


def test_mirror_stores_whole_response_with_nulls(mirrored):
    garmin, _ = mirrored
    result = garmin.get_sleep_data("2026-10-22")
    assert result["missing"] is None  # caller still gets the normal response
    row = raw("raw_get_sleep_data", ["2026-10-22"])
    assert row["data"]["missing"] is None and "missing" in row["data"]  # key kept as NULL
    assert row["data"]["series"] == [[1, None, 3]]
    assert row["fetched_at"].tzinfo is not None


def test_refetch_replaces_the_raw_record(mirrored):
    garmin, _ = mirrored
    garmin.get_stats("2026-10-22")
    garmin.get_stats("2026-10-22")
    assert len(surreal_store._query("SELECT * FROM raw_get_stats;")[0]) == 1


def test_no_arg_calls_are_daily_snapshots_and_binary_is_skipped(mirrored):
    garmin, _ = mirrored
    garmin.get_personal_record()
    assert garmin.download_activity(1) == b"FITDATA"
    assert garmin.display_name == "abc"
    tables = surreal_store._query("INFO FOR DB;")[0]["tables"]
    assert "raw_get_personal_record" in tables and "raw_download_activity" not in tables


def test_connectapi_get_is_kept_but_post_is_not(mirrored):
    garmin, _ = mirrored
    garmin.connectapi("biometric-service/stats/x", params={"a": 1})
    garmin.connectapi("wellness-service/wellness/epoch/request/2026-10-22", method="POST")
    rows = surreal_store._query("SELECT VALUE id FROM raw_connectapi;")[0]
    assert len(rows) == 1 and rows[0].id[0] == "biometric-service/stats/x"


def test_extras_cover_day_activities_and_snapshots_once(mirrored):
    garmin, fake = mirrored
    garmin.get_activities_by_date("2026-10-22", "2026-10-22")  # as upstream's activity fetch does
    garmin_raw.fetch_extras(garmin, "2026-10-22")
    names = [n for n, _ in fake.calls]
    assert names.count("get_activities_by_date") == 1  # reused, not called again
    assert {("get_activity_weather", ("111",)), ("get_activity_weather", ("222",))} <= set(fake.calls)
    assert ("get_device_settings", ("9",)) in fake.calls and ("get_gear", ("77",)) in fake.calls
    assert "raw_get_floors" not in surreal_store._query("INFO FOR DB;")[0]["tables"]  # skipped, no crash
    before = len(fake.calls)
    garmin_raw.fetch_extras(garmin, "2026-10-21")
    snapshot_names = {m for m, _ in garmin_raw.EXTRA_SNAPSHOT}
    assert snapshot_names & {n for n, _ in fake.calls[:before]}  # taken on the first day
    snapshot_calls = [n for n, _ in fake.calls[before:] if n in snapshot_names]
    assert snapshot_calls == []  # once per UTC day


def test_rate_limit_still_reaches_upstream_retry(mirrored, monkeypatch):
    garmin, fake = mirrored

    def limited(*args):
        raise GarminConnectTooManyRequestsError("429")
    monkeypatch.setattr(fake, "get_spo2_data", limited, raising=False)
    with pytest.raises(GarminConnectTooManyRequestsError):
        garmin_raw.fetch_extras(garmin, "2026-10-22")


def test_raw_write_failure_inside_upstream_try_still_retries_the_date(mirrored, monkeypatch):
    garmin, _ = mirrored
    calls = []

    def broken(*args):
        calls.append(args)
        raise surreal_store.SurrealStoreError("SurrealDB unreachable")
    monkeypatch.setattr(surreal_store, "write_raw", broken)
    try:  # upstream wraps some Garmin calls like this and would swallow the error
        garmin.get_lifestyle_logging_data("2026-10-22")
    except Exception:
        pytest.fail("the mirror must not raise inside upstream code")
    garmin.get_stats("2026-10-22")
    assert len(calls) == 1  # no more write attempts once one failed
    with pytest.raises(surreal_store.SurrealStoreError):
        garmin_raw.raise_pending()
    garmin_raw.raise_pending()  # cleared


def test_refetch_with_less_data_keeps_the_fuller_copy(mirrored):
    full = {"heartRateValues": [[1, 60], [2, 61]], "restingHeartRate": 55}
    surreal_store.write_raw("get_heart_rates", ["2025-01-01"], full)
    surreal_store.write_raw("get_heart_rates", ["2025-01-01"], {"heartRateValues": None, "restingHeartRate": 55})
    surreal_store.write_raw("get_heart_rates", ["2025-01-01"], None)
    history = surreal_store._query("SELECT data, leaves FROM raw_history ORDER BY leaves DESC;")[0]
    assert history[0]["data"] == full and history[0]["leaves"] == 5
    current = raw("raw_get_heart_rates", ["2025-01-01"])
    assert current["data"] is None  # newest response is still the main copy


def test_growing_data_does_not_fill_history(mirrored):
    surreal_store.write_raw("get_stats", ["2026-10-23"], {"steps": 100})
    surreal_store.write_raw("get_stats", ["2026-10-23"], {"steps": 900, "floors": 3})
    assert surreal_store._query("SELECT * FROM raw_history;")[0] == []


def test_snapshots_are_keyed_by_day_goals_all_statuses_and_workouts_paged(mirrored, monkeypatch):
    garmin, fake = mirrored
    pages = {0: [{"workoutId": i} for i in range(100)], 100: [{"workoutId": 100}]}
    monkeypatch.setattr(fake, "get_workouts", lambda start, limit: pages[start], raising=False)
    garmin_raw.fetch_extras(garmin, "2026-10-22")
    day = garmin_raw._today()
    assert raw("raw_get_device_settings", ["9", day]) is not None
    assert {tuple(r.id) for r in surreal_store._query("SELECT VALUE id FROM raw_get_goals;")[0]} == \
        {("active", day), ("future", day), ("past", day)}
    assert len(surreal_store._query("SELECT * FROM raw_get_workouts;")[0]) == 2


def test_polling_calls_are_not_mirrored(mirrored):
    garmin, _ = mirrored
    garmin.get_device_last_used()
    assert "raw_get_device_last_used" not in surreal_store._query("INFO FOR DB;")[0]["tables"]


def test_auth_error_in_extras_reaches_upstream_relogin(mirrored, monkeypatch):
    from garminconnect import GarminConnectAuthenticationError
    garmin, fake = mirrored

    def expired(*args):
        raise GarminConnectAuthenticationError("401")
    monkeypatch.setattr(fake, "get_floors", expired, raising=False)
    with pytest.raises(GarminConnectAuthenticationError):
        garmin_raw.fetch_extras(garmin, "2026-10-22")
