"""Unit testy pro sync_pohoda_to_bigquery (bez živých připojení)."""

import decimal
import json
import uuid

import pandas as pd
import pytest

import sync_pohoda_to_bigquery as s


# --- load_config ----------------------------------------------------------

def test_load_config_array(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps([{"name": "a"}, {"name": "b"}]), encoding="utf-8")
    blocks = s.load_config(str(p))
    assert [b["name"] for b in blocks] == ["a", "b"]


def test_load_config_single_object_wrapped(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"name": "solo"}), encoding="utf-8")
    blocks = s.load_config(str(p))
    assert isinstance(blocks, list) and len(blocks) == 1
    assert blocks[0]["name"] == "solo"


# --- dedupe_columns -------------------------------------------------------

def test_dedupe_columns():
    assert s.dedupe_columns(["A", "B", "A", "A", "C"]) == ["A", "B", "A_1", "A_2", "C"]


# --- prepare_sql ----------------------------------------------------------

def test_prepare_sql_prefix_and_days_back():
    sql = "SELECT * FROM FA h LEFT JOIN FApol r ON r.RefAg = h.ID WHERE x >= GETDATE() - <DAYS_BACK>"
    out = s.prepare_sql(sql, "SRV", "pohoda_2025", 14)
    assert "FROM [SRV].[pohoda_2025].dbo.FA" in out
    assert "JOIN [SRV].[pohoda_2025].dbo.FApol" in out
    assert "<DAYS_BACK>" not in out
    assert "GETDATE() - 14" in out


def test_prepare_sql_no_placeholder_is_noop_window():
    sql = "SELECT * FROM SKz skz LEFT JOIN sSklad skl ON skl.ID = skz.RefSklad"
    out = s.prepare_sql(sql, "SRV", "db", 4000)
    assert "FROM [SRV].[db].dbo.SKz" in out
    assert "JOIN [SRV].[db].dbo.sSklad" in out


# --- build_bq_schema ------------------------------------------------------

def test_build_bq_schema_types():
    schema = s.build_bq_schema(["ID", "Datum", "Mnozstvi", "Kc", "Firma"])
    by_name = {f.name: f.field_type for f in schema}
    assert by_name["Datum"] == "TIMESTAMP"
    assert by_name["Mnozstvi"] == "FLOAT64"
    assert by_name["Kc"] == "FLOAT64"
    assert by_name["ID"] == "STRING"
    assert by_name["Firma"] == "STRING"


def test_build_bq_schema_dedup_base():
    # Datum_1 (po dedupe) musí být stále TIMESTAMP díky base-name detekci
    schema = s.build_bq_schema(["Datum", "Datum_1"])
    assert all(f.field_type == "TIMESTAMP" for f in schema)


# --- prepare_dataframe ----------------------------------------------------

def test_prepare_dataframe_types_and_nulls():
    g = uuid.uuid4()
    df = pd.DataFrame({
        "ID": ["FA-1", None],
        "GUID": [g.bytes_le, None],
        "Mnozstvi": [decimal.Decimal("2.5"), None],
        "Kc": ["3.0", None],
        "Datum": ["2025-01-15", None],
        "Text": [decimal.Decimal("10"), float("nan")],
    })
    out = s.prepare_dataframe(df)

    assert out["ID"].iloc[0] == "FA-1"
    assert pd.isna(out["ID"].iloc[1])
    assert out["GUID"].iloc[0] == str(g)
    assert pd.isna(out["GUID"].iloc[1])
    assert out["Mnozstvi"].iloc[0] == 2.5
    assert pd.isna(out["Mnozstvi"].iloc[1])
    assert out["Kc"].iloc[0] == 3.0
    assert str(out["Datum"].dtype).startswith("datetime")
    # ostatní sloupce jako string
    assert out["Text"].iloc[0] == "10"
    assert pd.isna(out["Text"].iloc[1])


def test_prepare_dataframe_duplicate_columns():
    df = pd.DataFrame([[1, 2]], columns=["RefZeme", "RefZeme"])
    out = s.prepare_dataframe(df)
    assert list(out.columns) == ["RefZeme", "RefZeme_1"]


# --- databases_to_process -------------------------------------------------

DBS = {
    "current": {"linked_server": "SRV", "database": "pohoda_2025"},
    "history": [
        {"linked_server": "SRV", "database": "pohoda_2024"},
        {"linked_server": "SRV", "database": "pohoda_2023"},
    ],
}


def test_databases_normal_run_current_only():
    out = s.databases_to_process(DBS, backfill=False)
    assert [d["database"] for d in out] == ["pohoda_2025"]


def test_databases_backfill_current_last():
    out = s.databases_to_process(DBS, backfill=True)
    assert [d["database"] for d in out] == ["pohoda_2024", "pohoda_2023", "pohoda_2025"]


def test_databases_filter():
    out = s.databases_to_process(DBS, backfill=True, database_filter="pohoda_2024")
    assert [d["database"] for d in out] == ["pohoda_2024"]


# --- build_finalize_statements --------------------------------------------

def test_finalize_full_normal_replaces():
    stmts = s.build_finalize_statements("full", False, "p.d.FA", "p.d.FA_temp", "ID", ["ID", "Kc"])
    assert len(stmts) == 1
    assert stmts[0].startswith("CREATE OR REPLACE TABLE `p.d.FA`")
    assert "SELECT * FROM `p.d.FA_temp`" in stmts[0]


def test_finalize_incremental_merge():
    stmts = s.build_finalize_statements("incremental", False, "p.d.FA", "p.d.FA_temp", "ID", ["ID", "Kc", "Datum"])
    assert "CREATE TABLE IF NOT EXISTS" in stmts[0]
    merge = stmts[1]
    assert "MERGE `p.d.FA` T" in merge
    assert "ON T.`ID` = S.`ID`" in merge
    # zdroj je deduplikovaný na klíč (jinak BQ MERGE selže na duplicitních ID)
    assert "QUALIFY ROW_NUMBER() OVER (PARTITION BY `ID`" in merge
    # key (ID) se v UPDATE SET NEobjeví, ostatní sloupce ano
    set_clause = merge.split("UPDATE SET")[1].split("WHEN NOT MATCHED")[0]
    assert "T.`Kc` = S.`Kc`" in set_clause
    assert "T.`Datum` = S.`Datum`" in set_clause
    assert "`ID`" not in set_clause


def test_finalize_backfill_full_appends():
    stmts = s.build_finalize_statements("full", True, "p.d.FA", "p.d.FA_temp", "ID", ["ID", "Kc"])
    assert "CREATE TABLE IF NOT EXISTS" in stmts[0]
    assert stmts[1].startswith("INSERT INTO `p.d.FA`")
    assert "SELECT * FROM `p.d.FA_temp`" in stmts[1]


def test_finalize_backfill_incremental_still_merge():
    stmts = s.build_finalize_statements("incremental", True, "p.d.FA", "p.d.FA_temp", "ID", ["ID", "Kc"])
    assert any("MERGE `p.d.FA` T" in st for st in stmts)
    assert not any("CREATE OR REPLACE" in st for st in stmts)
