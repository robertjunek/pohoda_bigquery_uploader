"""Pytest konfigurace - nastrčí lehké faky za těžké závislosti (pyodbc, sentry,
google-cloud-bigquery), aby unit testy běžely bez živých připojení i bez nutnosti
mít nainstalované celé SDK. Testuje se čistá logika skriptu."""

import sys
import types
from pathlib import Path

# Repo root na sys.path, ať jde importovat sync_pohoda_to_bigquery.
sys.path.insert(0, str(Path(__file__).parent))


def _fake_module(name):
    mod = types.ModuleType(name)
    sys.modules[name] = mod
    return mod


# --- pyodbc ---------------------------------------------------------------
_pyodbc = _fake_module("pyodbc")
_pyodbc.Error = Exception
_pyodbc.connect = lambda *a, **k: None

# --- sentry_sdk -----------------------------------------------------------
_sentry = _fake_module("sentry_sdk")
_sentry.init = lambda *a, **k: None
_sentry.capture_exception = lambda *a, **k: None
_sentry.capture_message = lambda *a, **k: None


# --- google.cloud.bigquery ------------------------------------------------
class _SchemaField:
    def __init__(self, name, field_type, mode="NULLABLE"):
        self.name = name
        self.field_type = field_type
        self.mode = mode


class _WriteDisposition:
    WRITE_APPEND = "WRITE_APPEND"
    WRITE_TRUNCATE = "WRITE_TRUNCATE"


class _LoadJobConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Table:
    def __init__(self, table_id, schema=None):
        self.table_id = table_id
        self.schema = schema or []


class _Dataset:
    def __init__(self, ref):
        self.ref = ref
        self.location = None


class _Client:
    def __init__(self, *a, **k):
        pass


_google = _fake_module("google")
_google_cloud = _fake_module("google.cloud")
_google.cloud = _google_cloud

_bigquery = _fake_module("google.cloud.bigquery")
_bigquery.SchemaField = _SchemaField
_bigquery.WriteDisposition = _WriteDisposition
_bigquery.LoadJobConfig = _LoadJobConfig
_bigquery.Table = _Table
_bigquery.Dataset = _Dataset
_bigquery.Client = _Client
_google_cloud.bigquery = _bigquery

_exceptions = _fake_module("google.cloud.exceptions")
_exceptions.NotFound = type("NotFound", (Exception,), {})
_google_cloud.exceptions = _exceptions
