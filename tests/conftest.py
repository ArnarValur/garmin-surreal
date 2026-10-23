"""Test fixtures for the SurrealDB backend.

DB tests need a real SurrealDB 3.x: the SDK's embedded mem:// engine is
SurrealDB 2.0, which handles ID ranges and missing tables differently.
Set TEST_SURREALDB_URI (root/root login) to use a running server; otherwise a
throwaway surrealdb/surrealdb container is started. Tests skip when neither works.
"""

import os
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "garmin_grafana"))

import surreal_store  # noqa: E402
from surrealdb import Surreal  # noqa: E402

SURREALDB_IMAGE = os.getenv("TEST_SURREALDB_IMAGE", "surrealdb/surrealdb:v3.2.4")
ROOT = {"username": "root", "password": "root"}


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(uri, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            db = Surreal(uri)
            db.signin(ROOT)
            db.close()
            return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def surreal_uri():
    uri = os.getenv("TEST_SURREALDB_URI")
    if uri:
        if not _wait_ready(uri, timeout=5):
            pytest.skip(f"TEST_SURREALDB_URI={uri} is not reachable with root/root")
        yield uri
        return
    if not shutil.which("docker"):
        pytest.skip("docker not available and TEST_SURREALDB_URI not set")
    port = _free_port()
    name = f"garmin-surreal-test-{uuid.uuid4().hex[:8]}"
    started = subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{port}:8000",
         SURREALDB_IMAGE, "start", "--user", "root", "--pass", "root", "memory"],
        capture_output=True, text=True)
    if started.returncode != 0:
        pytest.skip(f"could not start {SURREALDB_IMAGE}: {started.stderr.strip()}")
    uri = f"ws://127.0.0.1:{port}/rpc"
    try:
        if not _wait_ready(uri):
            pytest.skip(f"{SURREALDB_IMAGE} did not become ready")
        yield uri
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True)


@pytest.fixture
def root_db(surreal_uri):
    """Root connection inside a fresh, uniquely named namespace (removed afterwards)."""
    ns = f"test_{uuid.uuid4().hex[:10]}"
    db = Surreal(surreal_uri)
    db.signin(ROOT)
    db.use(ns, "garmin")
    db.query_raw("DEFINE NAMESPACE IF NOT EXISTS " + ns + "; USE NS " + ns + "; DEFINE DATABASE IF NOT EXISTS garmin;")
    yield db, ns
    db.query_raw(f"REMOVE NAMESPACE IF EXISTS {ns};")
    db.close()


@pytest.fixture
def store(surreal_uri, root_db):
    """surreal_store connected as root to the test namespace."""
    _, ns = root_db
    surreal_store.connect({"uri": surreal_uri, "namespace": ns, "database": "garmin",
                           "user": "root", "password": "root", "batch_size": 2000})
    yield surreal_store
    surreal_store._close()


def rows(db, sql):
    """Run one statement on a raw SDK connection and return its rows."""
    response = db.query_raw(sql)
    statement = response["result"][-1]
    assert statement["status"] == "OK", statement
    return statement["result"]
