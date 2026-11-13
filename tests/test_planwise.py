import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from planwise import Analysis, PlanError, analyze, at_or_above, render_json, render_text
from planwise.cli import main


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, age INTEGER, city TEXT);"
        "CREATE INDEX users_email ON users(email);"
    )
    connection.executemany(
        "INSERT INTO users (email, age, city) VALUES (?, ?, ?)",
        [(f"u{i}@example.com", 20 + i % 40, "Cairo") for i in range(1, 1501)],
    )
    connection.commit()
    yield connection
    connection.close()


def test_full_scan_is_flagged_high_on_large_table(conn):
    analysis = analyze(conn, "SELECT * FROM users WHERE city = 'Cairo'")
    kinds = {f.kind for f in analysis.findings}
    assert "full-scan" in kinds
    scan = next(f for f in analysis.findings if f.kind == "full-scan")
    assert scan.table == "users"
    assert scan.severity == "high"
    assert analysis.row_counts["users"] == 1500
    assert any("idx_users_city" in s for s in analysis.suggestions)


def test_small_table_scan_is_medium(conn):
    conn.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, label TEXT)")
    conn.executemany("INSERT INTO tags (label) VALUES (?)", [("a",), ("b",)])
    conn.commit()
    analysis = analyze(conn, "SELECT * FROM tags WHERE label = 'a'", row_threshold=1000)
    scan = next(f for f in analysis.findings if f.kind == "full-scan")
    assert scan.severity == "medium"


def test_indexed_lookup_has_no_findings(conn):
    analysis = analyze(conn, "SELECT * FROM users WHERE email = 'u1@example.com'")
    assert analysis.findings == []
    assert analysis.suggestions == []
    assert analysis.worst == "none"


def test_order_by_temp_btree_is_reported_with_index_hint(conn):
    analysis = analyze(conn, "SELECT id FROM users ORDER BY age")
    kinds = {f.kind for f in analysis.findings}
    assert "temp-btree-order" in kinds
    assert any("idx_users_age" in s for s in analysis.suggestions)
    text = render_text(analysis, "users")
    assert "Suggested indexes" in text


def test_thresholds_and_rendering(conn):
    analysis = analyze(conn, "SELECT * FROM users WHERE city = 'Cairo'")
    assert len(at_or_above(analysis.findings, "high")) == 1
    assert at_or_above(analysis.findings, "none") == []
    payload = render_json(analysis, "users")
    assert '"worst": "high"' in payload
    assert '"findings"' in payload


def test_invalid_sql_raises_plan_error(conn):
    with pytest.raises(PlanError):
        analyze(conn, "SELECT * FROM missing_table")
    with pytest.raises(PlanError):
        analyze(conn, "   ")


def test_cli_check_and_exit_codes(tmp_path):
    database = tmp_path / "demo.db"
    connection = sqlite3.connect(database)
    connection.executescript("CREATE TABLE items (id INTEGER PRIMARY KEY, sku TEXT);")
    connection.executemany(
        "INSERT INTO items (sku) VALUES (?)", [(f"sku-{i}",) for i in range(1200)]
    )
    connection.commit()
    connection.close()

    sql = "SELECT * FROM items WHERE sku = 'sku-1'"
    assert main(["check", str(database), sql]) == 1
    assert main(["check", str(database), sql, "--fail-on", "none"]) == 0
    assert main(["check", str(database), sql, "--json"]) == 1

    query_file = tmp_path / "query.sql"
    query_file.write_text("SELECT id FROM items ORDER BY sku;\n", encoding="utf-8")
    assert main(["check", str(database), str(query_file)]) == 1

    assert main(["check", str(tmp_path / "nope.db"), sql]) == 2
    assert main(["check", str(database), "SELECT * FROM nope"]) == 2
    assert main(["demo"]) == 0
