"""SurrealDB storage backend for garmin-surreal (replaces InfluxDB).

Fetch functions keep upstream's InfluxDB point shape:
    {"measurement": str, "time": str|datetime|int, "tags": {...}, "fields": {...}}

Each measurement becomes a table. Each point becomes one record whose ID is an
array that starts with the UTC time, e.g. HeartRateIntraday:[d'2026-10-01T06:00:00Z'],
so a day reads as one ID range and re-fetching a day upserts the same records.

Write semantics mirror InfluxDB: None/NaN fields are skipped (they never wipe a
stored value), naive times are UTC, points with no fields are dropped, and two
writes of the same point merge field by field.
"""

import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone

from surrealdb import RecordID, Surreal

# Tags that tell apart points sharing one timestamp within a measurement.
# Kept out on purpose: Device, User_ID, ActivityName, ActivitySelector (they can
# drift between fetches and would duplicate rows) and Database_Name.
KEY_TAGS = (
    "ActivityID",        # every activity table: several activities can share a second
    "ExerciseCategory",  # StrengthExerciseSet (stale rows are purged by ActivityID first)
    "ExerciseLabel",     # StrengthExerciseSet
    "Source",            # BloodPressure: manual + synced reading in the same second
    "SourceType",        # BodyComposition: weigh-ins without a timestamp all sit at 00:00 UTC
    "behavior",          # LifestyleJournal: every behavior of a day sits at 00:00 UTC
)

# Fields that also go into the ID, per measurement (stable FIT message indexes).
# These keep apart zero-length laps/lengths and same-second strength sets,
# which InfluxDB merged.
KEY_FIELDS = {
    "ActivityLap": ("Index",),
    "ActivityLength": ("Index",),
    "ActivitySession": ("Index",),
    "StrengthExerciseSet": ("SetOrder",),
}

EXCLUDED_TAGS = ("Database_Name",)

UPSERT_ROWS = "FOR $r IN $rows { UPSERT $r.id MERGE $r.content; };"

# Waits between reconnect attempts (seconds) — rides out a SurrealDB restart.
RECONNECT_DELAYS = (0, 1, 2, 4, 8, 15)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_INT64_MIN, _INT64_MAX = -(2 ** 63), 2 ** 63 - 1

_db = None
_config = None


class SurrealStoreError(Exception):
    """A SurrealDB query or write failed."""


def _env_config():
    return {
        "uri": os.getenv("SURREALDB_URI", "ws://localhost:8000/rpc"),
        "namespace": os.getenv("SURREALDB_NS", "health"),
        "database": os.getenv("SURREALDB_DB", "garmin"),
        "user": os.getenv("SURREALDB_USER", ""),
        "password": os.getenv("SURREALDB_PASS", ""),
        "batch_size": int(os.getenv("SURREALDB_BATCH_SIZE", 2000)),
    }


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _signin(db, cfg):
    """Sign in as the dedicated database user, or as a root user as fallback."""
    if not cfg["user"]:
        return "none"
    try:
        db.signin({"namespace": cfg["namespace"], "database": cfg["database"],
                   "username": cfg["user"], "password": cfg["password"]})
        return "database"
    except Exception as db_err:
        try:
            db.signin({"username": cfg["user"], "password": cfg["password"]})
            return "root"
        except Exception:
            raise db_err


def _open(cfg):
    db = Surreal(cfg["uri"])
    level = _signin(db, cfg)
    db.use(cfg["namespace"], cfg["database"])
    return db, level


def _close():
    global _db
    if _db is not None:
        try:
            _db.close()
        except Exception:
            pass
    _db = None


def connect(config=None):
    """Open the connection and prove it can write to SURREALDB_NS/SURREALDB_DB.

    A database user pointed at the wrong namespace/database gets no error from
    SurrealDB, its writes just vanish, so the check upserts a meta record and
    requires it back.
    """
    global _db, _config
    _close()
    _config = config or _env_config()
    cfg = _config
    target = f"{cfg['uri']} (ns={cfg['namespace']}, db={cfg['database']})"
    try:
        _db, level = _open(cfg)
        checked = _query("UPSERT meta:connection MERGE { checked_at: time::now() } RETURN AFTER;")
        if not checked or not checked[0]:
            raise SurrealStoreError("write check returned nothing — is the user allowed on this namespace/database?")
    except Exception as err:
        _close()
        logging.error(f"Unable to connect with SurrealDB at {target}! Aborted")
        raise SurrealStoreError(f"SurrealDB connection failed: {err}") from err
    logging.info(f"Connected to SurrealDB at {target} as {level} user")


def _is_transport_error(err):
    name = type(err).__name__
    return isinstance(err, (ConnectionError, OSError)) or name.startswith("ConnectionClosed") \
        or name in ("InvalidStatus", "InvalidHandshake", "ConnectionUnavailableError")


def _is_missing_table(err):
    return "does not exist" in str(err) and "table" in str(err).lower()


def _query_once(sql, params):
    response = _db.query_raw(sql, params or {})
    if response.get("error"):
        raise SurrealStoreError(f"RPC error: {response['error']}")
    results = []
    # db.query() only checks the first statement, so check every one here.
    for statement in response.get("result") or []:
        if statement.get("status") == "ERR":
            raise SurrealStoreError(str(statement.get("result")))
        results.append(statement.get("result"))
    return results


def _reconnect():
    """Replace the connection, retrying with backoff. Raises SurrealStoreError."""
    global _db
    _close()
    last_err = None
    for delay in RECONNECT_DELAYS:
        time.sleep(delay)
        try:
            _db, _ = _open(_config)
            logging.info("Reconnected to SurrealDB")
            return
        except Exception as err:
            last_err = err
    raise SurrealStoreError(f"SurrealDB unreachable: {type(last_err).__name__}: {last_err}") from last_err


def _query(sql, params=None):
    """Run a query, raising SurrealStoreError on any failure; reconnects if the socket died."""
    if _config is None:
        raise SurrealStoreError("Not connected — call surreal_store.connect() first")
    if _db is None:  # an earlier reconnect failed — try again now
        _reconnect()
    try:
        return _query_once(sql, params)
    except SurrealStoreError:
        raise
    except Exception as err:
        if not _is_transport_error(err):
            raise SurrealStoreError(f"{type(err).__name__}: {err}") from err
        logging.warning(f"SurrealDB connection lost ({type(err).__name__}: {err}) — reconnecting")
    _reconnect()
    try:
        return _query_once(sql, params)
    except SurrealStoreError:
        raise
    except Exception as err:
        raise SurrealStoreError(f"{type(err).__name__}: {err}") from err


# ---------------------------------------------------------------------------
# Point -> row mapping
# ---------------------------------------------------------------------------

def to_utc_datetime(value):
    """Point time -> aware UTC datetime, the way the InfluxDB client read it.

    Strings are ISO 8601; naive strings and datetimes count as UTC; ints are
    epoch nanoseconds. Returns None when there is no usable time.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    elif isinstance(value, int) and not isinstance(value, bool):
        seconds, nanos = divmod(value, 10 ** 9)
        return _EPOCH + timedelta(seconds=seconds, microseconds=nanos // 1000)
    else:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean_field(value):
    """Return the value to store, or None to skip it (InfluxDB never stored these)."""
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, int) and not isinstance(value, bool) and not _INT64_MIN <= value <= _INT64_MAX:
        return float(value)  # SurrealDB would silently wrap it
    return value


def _key_part(value):
    return value if isinstance(value, str) else str(value)


def point_to_row(point):
    """Map one point to {"table", "key", "content"}, or None if InfluxDB would not store it."""
    measurement = point.get("measurement")
    when = to_utc_datetime(point.get("time"))
    if not measurement or when is None:
        logging.warning(f"Skipped : point without measurement or usable time: "
                        f"{measurement!r} {point.get('time')!r}")
        return None
    fields = {}
    for name, value in (point.get("fields") or {}).items():
        value = _clean_field(value)
        if value is not None:
            fields[name] = value
    if not fields:
        return None
    tags = {name: value for name, value in (point.get("tags") or {}).items()
            if name not in EXCLUDED_TAGS and value is not None and value != ""}
    key = [when]
    key += [_key_part(tags[name]) for name in sorted(tags) if name in KEY_TAGS]
    key += [_key_part(fields.get(name, "")) for name in KEY_FIELDS.get(measurement, ())]
    return {"table": measurement, "key": key,
            "content": {**fields, "time": when, "tags": tags}}


def points_to_rows(points):
    """Map points to upsert rows, merging points that share a record ID.

    Merging follows InfluxDB: later points win field by field. Two different
    values for the same field under one ID mean a point would be lost, so that
    is logged as a collision.
    """
    rows = {}
    collisions = 0
    for point in points:
        row = point_to_row(point)
        if row is None:
            continue
        rid = (row["table"], tuple(row["key"]))
        existing = rows.get(rid)
        if existing is None:
            rows[rid] = row
            continue
        content = existing["content"]
        for name, value in row["content"].items():
            if name == "tags":
                content["tags"] = {**content["tags"], **value}
            elif name != "time" and name in content and content[name] != value:
                collisions += 1
                if collisions <= 5:
                    logging.warning(f"Collision : {row['table']}:{row['key']} field {name!r} "
                                    f"{content[name]!r} -> {value!r} (later point wins)")
                content[name] = value
            else:
                content[name] = value
    if collisions > 5:
        logging.warning(f"Collision : {collisions} field overwrites in total in this write")
    return [{"id": RecordID(r["table"], r["key"]), "content": r["content"]} for r in rows.values()]


# ---------------------------------------------------------------------------
# Public API used by garmin_fetch.py
# ---------------------------------------------------------------------------

def write_points(points):
    """Upsert-merge points in batches. Raises SurrealStoreError on failure."""
    rows = points_to_rows(points)
    if not rows:
        return 0
    batch_size = max(1, (_config or _env_config())["batch_size"])
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        try:
            _query(UPSERT_ROWS, {"rows": batch})
        except Exception as err:
            tables = sorted({str(r["id"].table_name) for r in batch})
            raise SurrealStoreError(f"Write failed for {len(batch)} rows of {', '.join(tables)}: {err}") from err
    tables = sorted({str(r["id"].table_name) for r in rows})
    logging.info(f"Success : upserted {len(rows)} rows ({len(points)} points) into SurrealDB {', '.join(tables)}")
    return len(rows)


def last_sync_time(table="HeartRateIntraday"):
    """Time of the newest record in a table, or None if it is empty or missing."""
    try:
        result = _query(f"SELECT id, time FROM {table} ORDER BY id DESC LIMIT 1;")
    except SurrealStoreError as err:
        if _is_missing_table(err):
            return None
        raise
    rows = result[0] if result else []
    if not rows:
        return None
    return to_utc_datetime(rows[0].get("time"))


def purge_strength_sets(activity_id):
    """Delete stored StrengthExerciseSet rows of one activity before re-writing it."""
    try:
        # The ActivityID tag is an int from the API but may be a string from other sources.
        ids = [str(activity_id)] + ([int(activity_id)] if str(activity_id).isdigit() else [])
        _query("DELETE StrengthExerciseSet WHERE tags.ActivityID IN $ids;", {"ids": ids})
    except SurrealStoreError as err:
        if _is_missing_table(err):
            return True
        logging.error(f"Failed to purge existing StrengthExerciseSet rows for activity {activity_id}: {err}")
        raise  # the caller retries the whole date instead of dropping the sets
    logging.info(f"Purged existing StrengthExerciseSet rows for activity {activity_id}")
    return True


def mark_sync_pending(start):
    """Remember where an update range starts, so a crash mid-range resumes from there."""
    _query("UPSERT meta:sync MERGE { pending_from: $t };", {"t": to_utc_datetime(start)})


def clear_sync_pending():
    _query("UPSERT meta:sync MERGE { pending_from: NONE, completed_at: time::now() };")


def pending_sync_from():
    """Start of an update range that never finished, or None."""
    result = _query("SELECT VALUE pending_from FROM meta:sync;")
    values = result[0] if result else []
    return to_utc_datetime(values[0]) if values else None
