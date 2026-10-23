#!/usr/bin/env python3
"""Row counts per table in SURREALDB_NS/SURREALDB_DB, optionally per UTC day.

Usage (with .env sourced): python scripts/table_counts.py [--days]
"""
import sys
from collections import Counter
sys.path.insert(0, "src/garmin_grafana")
import surreal_store as ss

ss.connect()
tables = sorted(t for t in ss._query("INFO FOR DB;")[0]["tables"] if t != "meta")
per_day = "--days" in sys.argv
for t in tables:
    times = ss._query(f"SELECT VALUE time FROM {t};")[0]
    line = f"{t:24} {len(times):>7}"
    if per_day:
        days = Counter(str(x)[:10] for x in times)
        line += "  " + " ".join(f"{d[5:]}:{n}" for d, n in sorted(days.items())[-10:])
    print(line)
