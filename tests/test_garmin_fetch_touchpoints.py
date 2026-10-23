"""garmin_fetch.py touch points, driven against a real SurrealDB 3.x."""

import importlib
import sys

import pytest

import surreal_store


@pytest.fixture
def garmin_fetch(surreal_uri, root_db, monkeypatch):
    _, ns = root_db
    for name, value in {"SURREALDB_URI": surreal_uri, "SURREALDB_NS": ns, "SURREALDB_DB": "garmin",
                        "SURREALDB_USER": "root", "SURREALDB_PASS": "root"}.items():
        monkeypatch.setenv(name, value)
    sys.modules.pop("garmin_fetch", None)
    module = importlib.import_module("garmin_fetch")  # connects at import, like the container
    yield module
    surreal_store._close()
    sys.modules.pop("garmin_fetch", None)


def point(day, value=1):
    return {"measurement": "DailyStats", "time": f"{day}T00:00:00+00:00",
            "tags": {"Device": "Venu 2 Plus", "Database_Name": "garmin"}, "fields": {"totalSteps": value}}


def stored_days():
    return sorted(str(t)[:10] for t in surreal_store._query("SELECT VALUE time FROM DailyStats;")[0])


def test_write_wrapper_upserts(garmin_fetch):
    garmin_fetch.write_points_to_influxdb([point("2026-10-01")])
    garmin_fetch.write_points_to_influxdb([point("2026-10-01", 2)])
    assert stored_days() == ["2026-10-01"]


@pytest.mark.parametrize("ignore_errors", [False, True])
def test_database_failure_retries_the_date_instead_of_skipping_it(garmin_fetch, monkeypatch, ignore_errors):
    monkeypatch.setattr(garmin_fetch, "IGNORE_ERRORS", ignore_errors)
    monkeypatch.setattr(garmin_fetch, "RATE_LIMIT_CALLS_SECONDS", 0)
    monkeypatch.setattr(garmin_fetch, "get_last_sync", lambda: [])
    monkeypatch.setattr(garmin_fetch.time, "sleep", lambda s: None)
    failures = {"2026-10-02": 1}

    def daily_fetch_write(day):
        if failures.get(day):
            failures[day] -= 1
            raise surreal_store.SurrealStoreError("Write failed: simulated outage")
        garmin_fetch.write_points_to_influxdb([point(day)])
    monkeypatch.setattr(garmin_fetch, "daily_fetch_write", daily_fetch_write)

    garmin_fetch.fetch_write_bulk("2026-10-01", "2026-10-03")
    assert stored_days() == ["2026-10-01", "2026-10-02", "2026-10-03"]


def test_strength_purge_runs_through_the_touch_point(garmin_fetch):
    sets = [{"measurement": "StrengthExerciseSet", "time": f"2026-10-01T07:00:0{i}+00:00",
             "tags": {"ActivityID": 5, "ExerciseCategory": "X", "ExerciseLabel": "Y"},
             "fields": {"SetOrder": i}} for i in range(3)]
    garmin_fetch.write_points_to_influxdb(sets)
    assert garmin_fetch.purge_existing_strength_exercise_sets(5) is True
    assert surreal_store._query("SELECT * FROM StrengthExerciseSet;")[0] == []


def test_intraday_refresh_uses_request_reload(garmin_fetch, monkeypatch):
    class Fake:
        reloads = []

        def request_reload(self, day):
            self.reloads.append(day)
            return {"status": "COMPLETE"}
    fake = Fake()
    monkeypatch.setattr(garmin_fetch, "garmin_obj", fake)
    monkeypatch.setattr(garmin_fetch, "REQUEST_INTRADAY_DATA_REFRESH", True)
    monkeypatch.setattr(garmin_fetch, "FETCH_SELECTION", "")
    garmin_fetch.daily_fetch_write("2025-01-01")
    assert fake.reloads == ["2025-01-01"]
