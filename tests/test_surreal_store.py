"""Tests for surreal_store: point mapping (no server) and writes against SurrealDB 3.x."""

import logging
import math
from datetime import datetime, timedelta, timezone

import pytest
from surrealdb import Surreal

import surreal_store
from conftest import rows

UTC = timezone.utc
T0 = datetime(2026, 10, 1, 6, 0, tzinfo=UTC)


def hr_point(minute, value=60, device="Venu 2 Plus", **fields):
    return {
        "measurement": "HeartRateIntraday",
        "time": (T0 + timedelta(minutes=minute)).isoformat(),
        "tags": {"Device": device, "Database_Name": "garmin"},
        "fields": {"HeartRate": value, **fields},
    }


def key_of(point):
    return surreal_store.point_to_row(point)["key"]


# ---------------------------------------------------------------------------
# Mapping — no server
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "2026-10-01T06:00:00+00:00",
    "2026-10-01T06:00:00.000000+00:00",
    "2026-10-01T06:00:00Z",
    "2026-10-01T08:00:00+02:00",
    "2026-10-01T06:00:00",                      # naive -> UTC, like the InfluxDB client
    datetime(2026, 10, 1, 6, 0),                # naive datetime -> UTC
    datetime(2026, 10, 1, 8, 0, tzinfo=timezone(timedelta(hours=2))),
    int(T0.timestamp()) * 10 ** 9,              # epoch nanoseconds
])
def test_time_forms_map_to_the_same_utc_instant(value):
    assert surreal_store.to_utc_datetime(value) == T0
    assert surreal_store.to_utc_datetime(value).tzinfo == UTC


def test_sub_second_precision_is_kept():
    # StrengthHRZones are spaced 1 ms apart; they must stay distinct.
    a = surreal_store.to_utc_datetime("2026-10-01T06:00:00.001000+00:00")
    b = surreal_store.to_utc_datetime("2026-10-01T06:00:00.002000+00:00")
    assert a != b


def test_point_without_usable_time_is_skipped(caplog):
    with caplog.at_level(logging.WARNING):
        assert surreal_store.point_to_row({**hr_point(0), "time": None}) is None
        assert surreal_store.point_to_row({**hr_point(0), "time": "not a time"}) is None
    assert "Skipped" in caplog.text


def test_none_nan_and_inf_fields_are_dropped():
    row = surreal_store.point_to_row(hr_point(0, a=None, b=float("nan"), c=float("inf"), d=0, e=False))
    assert set(row["content"]) == {"HeartRate", "d", "e", "time", "tags"}


def test_point_with_only_empty_fields_is_skipped():
    point = hr_point(0)
    point["fields"] = {"HeartRate": None, "x": float("nan")}
    assert surreal_store.point_to_row(point) is None


def test_out_of_range_int_becomes_float():
    row = surreal_store.point_to_row(hr_point(0, big=2 ** 64))
    assert type(row["content"]["big"]) is float and row["content"]["big"] == float(2 ** 64)


def test_tags_drop_database_name_none_and_empty():
    point = hr_point(0)
    point["tags"].update({"SourceType": None, "Frequency": ""})
    assert surreal_store.point_to_row(point)["content"]["tags"] == {"Device": "Venu 2 Plus"}


def test_device_is_not_part_of_the_id():
    assert key_of(hr_point(0, device="Unknown")) == key_of(hr_point(0, device="Venu 2 Plus")) == [T0]


def test_activity_id_int_and_str_give_the_same_key():
    base = {"measurement": "ActivitySummary", "time": T0.isoformat(), "fields": {"distance": 1.0}}
    a = {**base, "tags": {"ActivityID": 123, "ActivitySelector": "x-running"}}
    b = {**base, "tags": {"ActivityID": "123", "ActivitySelector": "y-walking"}}
    assert key_of(a) == key_of(b) == [T0, "123"]


def test_lifestyle_behaviors_on_one_day_stay_apart():
    # Upstream writes every behavior of a day at 00:00 UTC; only the tag differs.
    points = [{"measurement": "LifestyleJournal", "time": "2026-10-01T00:00:00+00:00",
               "tags": {"behavior": name, "category": "x"}, "fields": {"status": 1, "value": 1.0}}
              for name in ("Alcohol", "Caffeine", "Late meal")]
    assert len(surreal_store.points_to_rows(points)) == 3


def test_strength_sets_in_one_second_stay_apart():
    def strength(label, order):
        return {"measurement": "StrengthExerciseSet", "time": T0.isoformat(),
                "tags": {"ActivityID": 9, "ExerciseCategory": "SQUAT", "ExerciseLabel": label},
                "fields": {"SetOrder": order, "Reps": 5}}
    points = [strength("Squat", 1), strength("Squat", 2), strength("Goblet", 3)]
    assert len(surreal_store.points_to_rows(points)) == 3


def test_same_set_order_with_other_exercise_stays_apart():
    def strength(category, label):
        return {"measurement": "StrengthExerciseSet", "time": T0.isoformat(),
                "tags": {"ActivityID": 9, "ExerciseCategory": category, "ExerciseLabel": label},
                "fields": {"SetOrder": 1}}
    points = [strength("SQUAT", "Squat"), strength("SQUAT", "Goblet"), strength("LUNGE", "Squat")]
    assert len(surreal_store.points_to_rows(points)) == 3


@pytest.mark.parametrize("measurement,tag", [("BloodPressure", "Source"), ("BodyComposition", "SourceType")])
def test_same_second_readings_from_two_sources_stay_apart(measurement, tag):
    points = [{"measurement": measurement, "time": T0.isoformat(), "tags": {tag: source},
               "fields": {"value": 1}} for source in ("MANUAL", "INDEX_SCALE")]
    assert len(surreal_store.points_to_rows(points)) == 2


def test_key_does_not_depend_on_tag_order():
    a = {"measurement": "StrengthExerciseSet", "time": T0.isoformat(), "fields": {"SetOrder": 1},
         "tags": {"ExerciseLabel": "Squat", "ActivityID": 9, "ExerciseCategory": "SQUAT"}}
    b = {**a, "tags": {"ActivityID": 9, "ExerciseCategory": "SQUAT", "ExerciseLabel": "Squat"}}
    assert key_of(a) == key_of(b) == [T0, "9", "SQUAT", "Squat", "1"]


def test_zero_length_laps_stay_apart():
    laps = [{"measurement": "ActivityLap", "time": T0.isoformat(), "tags": {"ActivityID": 9},
             "fields": {"Index": i, "Distance": 0.0}} for i in (1, 2)]
    assert len(surreal_store.points_to_rows(laps)) == 2


def test_field_disjoint_points_merge_like_influxdb():
    # SleepIntraday sub-sources share timestamps and differ only in field names.
    a = {"measurement": "SleepIntraday", "time": T0.isoformat(), "tags": {}, "fields": {"spo2Reading": 95}}
    b = {"measurement": "SleepIntraday", "time": T0.isoformat(), "tags": {}, "fields": {"heartRate": 50}}
    merged = surreal_store.points_to_rows([a, b])
    assert len(merged) == 1
    assert merged[0]["content"]["spo2Reading"] == 95 and merged[0]["content"]["heartRate"] == 50


def test_conflicting_values_under_one_id_are_logged(caplog):
    with caplog.at_level(logging.WARNING):
        merged = surreal_store.points_to_rows([hr_point(0, value=60), hr_point(0, value=70)])
    assert len(merged) == 1 and merged[0]["content"]["HeartRate"] == 70
    assert "Collision" in caplog.text


# ---------------------------------------------------------------------------
# Writes against a real SurrealDB 3.x
# ---------------------------------------------------------------------------

def count(store, table):
    return store._query(f"SELECT count() FROM {table} GROUP ALL;")[0][0]["count"]


def test_double_write_is_idempotent(store):
    points = [hr_point(m) for m in range(9)]
    store.write_points(points)
    store.write_points([hr_point(m) for m in range(9)])
    assert count(store, "HeartRateIntraday") == 9


def test_refetch_updates_tags_and_never_wipes_fields(store):
    store.write_points([hr_point(0, device="Unknown", restingHR=48)])
    store.write_points([hr_point(0, device="Venu 2 Plus", restingHR=None)])
    [row] = store._query("SELECT * FROM HeartRateIntraday;")[0]
    assert row["tags"]["Device"] == "Venu 2 Plus"
    assert row["restingHR"] == 48
    assert row["time"] == T0


def test_record_id_shape_and_types(store):
    store.write_points([{"measurement": "ActivityGPS", "time": T0.isoformat(),
                         "tags": {"ActivityID": 42, "ActivitySelector": "s"}, "fields": {"HeartRate": 120}}])
    [row] = store._query("SELECT * FROM ActivityGPS;")[0]
    assert row["id"].id == [T0, "42"]
    assert row["tags"] == {"ActivityID": 42, "ActivitySelector": "s"}
    assert store._query("RETURN type::of((SELECT VALUE id FROM ActivityGPS)[0].id()[0]);")[0] == "datetime"


def test_time_range_slice_on_record_id(store):
    store.write_points([hr_point(m * 60) for m in range(-3, 30)])  # hourly, from 03:00 on day 1
    day_start, day_end = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC)
    got = store._query("SELECT * FROM HeartRateIntraday:[$a]..[$b];", {"a": day_start, "b": day_end})[0]
    assert len(got) == 21  # 03:00 .. 23:00
    assert all(day_start <= r["time"] < day_end for r in got)


def test_range_slice_with_multi_part_ids(store):
    points = [{"measurement": "ActivityGPS", "time": (T0 + timedelta(hours=h)).isoformat(),
               "tags": {"ActivityID": a}, "fields": {"v": 1}} for h in (0, 17, 18) for a in (1, 2)]
    store.write_points(points)
    got = store._query("SELECT * FROM ActivityGPS:[$a]..[$b];",
                       {"a": T0, "b": datetime(2026, 10, 2, tzinfo=UTC)})[0]
    assert len(got) == 4  # 06:00 and 23:00, both activities; 00:00 next day excluded


def test_last_sync_time(store):
    assert store.last_sync_time() is None  # table does not exist yet
    store.write_points([hr_point(m) for m in (5, 1, 9, 3)])
    assert store.last_sync_time() == T0 + timedelta(minutes=9)


def test_purge_strength_sets(store):
    assert store.purge_strength_sets(7) is True  # table does not exist yet

    def strength(activity_id, order):
        return {"measurement": "StrengthExerciseSet", "time": (T0 + timedelta(seconds=order)).isoformat(),
                "tags": {"ActivityID": activity_id, "ExerciseCategory": "SQUAT", "ExerciseLabel": "Squat"},
                "fields": {"SetOrder": order, "Reps": 5}}
    store.write_points([strength(7, i) for i in range(3)] + [strength(8, i) for i in range(2)])
    assert store.purge_strength_sets(7) is True
    left = store._query("SELECT VALUE tags.ActivityID FROM StrengthExerciseSet;")[0]
    assert sorted(left) == [8, 8]
    assert store.purge_strength_sets("8") is True  # string id from the bulk importer
    assert store._query("SELECT * FROM StrengthExerciseSet;")[0] == []


def test_batching_across_chunk_boundary(store, monkeypatch):
    store._config["batch_size"] = 3
    sizes = []
    real_query = store._query

    def spy(sql, params=None):
        if sql == store.UPSERT_ROWS:
            sizes.append(len(params["rows"]))
        return real_query(sql, params)
    monkeypatch.setattr(store, "_query", spy)
    store.write_points([hr_point(m) for m in range(10)])
    assert sizes == [3, 3, 3, 1]
    assert count(store, "HeartRateIntraday") == 10


def test_purge_failure_raises(store, monkeypatch):
    def broken(sql, params=None):
        raise surreal_store.SurrealStoreError("IAM error: Not enough permissions")
    monkeypatch.setattr(store, "_query", broken)
    with pytest.raises(surreal_store.SurrealStoreError):
        store.purge_strength_sets(7)


def test_sync_pending_marker(store):
    assert store.pending_sync_from() is None
    store.mark_sync_pending(T0)
    assert store.pending_sync_from() == T0
    store.clear_sync_pending()
    assert store.pending_sync_from() is None


def test_large_gps_batch(store):
    points = [{"measurement": "ActivityGPS", "time": (T0 + timedelta(seconds=s)).isoformat(),
               "tags": {"ActivityID": 1}, "fields": {f"f{i}": float(i) for i in range(20)}}
              for s in range(25_000)]
    assert store.write_points(points) == 25_000
    assert count(store, "ActivityGPS") == 25_000


def test_failed_write_raises(store):
    store._query("DEFINE TABLE Strict SCHEMAFULL; DEFINE FIELD v ON Strict TYPE string;"
                 "DEFINE FIELD time ON Strict TYPE datetime; DEFINE FIELD tags ON Strict TYPE object FLEXIBLE;")
    bad = {"measurement": "Strict", "time": T0.isoformat(), "tags": {}, "fields": {"v": 123}}
    with pytest.raises(surreal_store.SurrealStoreError):
        store.write_points([bad])


def test_reconnects_after_dropped_socket(store):
    store.write_points([hr_point(0)])
    store._db.socket.close()  # simulate a dropped connection
    store.write_points([hr_point(1)])
    assert count(store, "HeartRateIntraday") == 2


def test_database_user_can_write_only_its_database(surreal_uri, root_db):
    db, ns = root_db
    rows(db, "DEFINE USER garmin_writer ON DATABASE PASSWORD 'pw' ROLES EDITOR;")
    cfg = {"uri": surreal_uri, "namespace": ns, "database": "garmin",
           "user": "garmin_writer", "password": "pw", "batch_size": 2000}
    surreal_store.connect(cfg)
    try:
        surreal_store.write_points([hr_point(0)])
        assert surreal_store.last_sync_time() == T0
    finally:
        surreal_store._close()
    with pytest.raises(surreal_store.SurrealStoreError):
        surreal_store.connect({**cfg, "database": "not_garmin"})  # the user only exists on "garmin"
    with pytest.raises(surreal_store.SurrealStoreError):
        surreal_store.connect({**cfg, "password": "wrong"})


def test_read_only_user_fails_the_write_check(surreal_uri, root_db):
    db, ns = root_db
    rows(db, "DEFINE USER garmin_viewer ON DATABASE PASSWORD 'pw' ROLES VIEWER;")
    with pytest.raises(surreal_store.SurrealStoreError, match="write check returned nothing|permissions"):
        surreal_store.connect({"uri": surreal_uri, "namespace": ns, "database": "garmin",
                               "user": "garmin_viewer", "password": "pw", "batch_size": 2000})
    assert surreal_store._db is None


def test_connect_fails_fast_when_server_is_down():
    with pytest.raises(surreal_store.SurrealStoreError):
        surreal_store.connect({"uri": "ws://127.0.0.1:9/rpc", "namespace": "health", "database": "garmin",
                               "user": "x", "password": "y", "batch_size": 2000})


def test_mem_engine_smoke():
    """Spec T1: the SDK's embedded engine (SurrealDB 2.0) also takes the upserts."""
    surreal_store.connect({"uri": "mem://", "namespace": "health", "database": "garmin",
                           "user": "", "password": "", "batch_size": 4})
    try:
        surreal_store.write_points([hr_point(m) for m in range(9)])
        surreal_store.write_points([hr_point(m) for m in range(9)])
        assert len(surreal_store._query("SELECT * FROM HeartRateIntraday;")[0]) == 9
    finally:
        surreal_store._close()


# ---------------------------------------------------------------------------
# Outages — a dedicated server that the test stops and starts
# ---------------------------------------------------------------------------

@pytest.fixture
def own_server():
    import shutil, subprocess, uuid
    from conftest import SURREALDB_IMAGE, _free_port, _wait_ready
    if not shutil.which("docker"):
        pytest.skip("docker not available")
    port, name = _free_port(), f"garmin-surreal-outage-{uuid.uuid4().hex[:8]}"
    started = subprocess.run(["docker", "run", "-d", "--name", name, "-p", f"127.0.0.1:{port}:8000",
                              SURREALDB_IMAGE, "start", "--user", "root", "--pass", "root", "memory"],
                             capture_output=True, text=True)
    if started.returncode != 0:
        pytest.skip(started.stderr.strip())
    uri = f"ws://127.0.0.1:{port}/rpc"
    assert _wait_ready(uri)
    docker = lambda *args: subprocess.run(["docker", *args, name], capture_output=True, check=True)
    yield uri, docker, lambda: _wait_ready(uri)
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    surreal_store._close()


def test_writes_resume_after_server_restart(own_server):
    uri, docker, wait_ready = own_server
    surreal_store.connect({"uri": uri, "namespace": "health", "database": "garmin",
                           "user": "root", "password": "root", "batch_size": 2000})
    surreal_store.write_points([hr_point(0)])
    docker("restart")  # memory storage: the restarted server is empty
    assert wait_ready()
    surreal_store.write_points([hr_point(1)])  # dead socket -> reconnect -> write
    assert surreal_store.last_sync_time() == T0 + timedelta(minutes=1)


def test_store_recovers_after_a_longer_outage(own_server, monkeypatch):
    uri, docker, wait_ready = own_server
    monkeypatch.setattr(surreal_store, "RECONNECT_DELAYS", (0, 0.2))
    surreal_store.connect({"uri": uri, "namespace": "health", "database": "garmin",
                           "user": "root", "password": "root", "batch_size": 2000})
    docker("stop")
    with pytest.raises(surreal_store.SurrealStoreError):
        surreal_store.write_points([hr_point(0)])
    with pytest.raises(surreal_store.SurrealStoreError):
        surreal_store.purge_strength_sets(1)  # same error type for every caller
    docker("start")
    assert wait_ready()
    surreal_store.write_points([hr_point(2)])  # no connect() needed — reconnects on its own
    assert surreal_store.last_sync_time() == T0 + timedelta(minutes=2)
