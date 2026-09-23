"""Alembic migration zinciri tutarlılığı.

Amaç: yeni migration eklendiğinde revision/dosya adı çakışması ve çoklu head
kazasının CI'da yakalanması. Mevcut (tarihsel) çakışmalar burada belgelenir;
test onları düzeltmeye çalışmaz, yalnızca yeni çakışmayı engeller.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"

# Bilinen tarihsel istisnalar (düzeltilmesi riskli; yeni eklenenler bu listeye giremez).
KNOWN_DUPLICATE_FILE_PREFIXES: set[str] = {"0105", "0072", "0095"}
KNOWN_MISSING_DOWN_REVISIONS: set[str] = set()


def _migration_files() -> list[Path]:
    return sorted(path for path in VERSIONS.glob("*.py") if path.name != "__init__.py")


def _read_source(path: Path) -> str:
    """BOM ve mojibake içeren tarihsel migration'ları tolere ederek okur."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def _literal(path: Path, name: str) -> str | None:
    """Modül düzeyindeki ``name = "..."`` veya ``name: str = "..."`` değerini okur."""
    try:
        tree = ast.parse(_read_source(path))
    except SyntaxError:
        return None
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and target.id == name and isinstance(value, ast.Constant):
            raw = value.value
            return None if raw is None else str(raw)
    return None


def test_versions_directory_exists():
    assert VERSIONS.is_dir()
    assert _migration_files()


def test_every_migration_has_revision_id():
    missing = [path.name for path in _migration_files() if not _literal(path, "revision")]
    assert missing == [], f"revision tanımlanmamış migration'lar: {missing}"


def test_every_migration_has_downgrade():
    missing = []
    for path in _migration_files():
        tree = ast.parse(_read_source(path))
        has_downgrade = any(
            isinstance(node, ast.FunctionDef) and node.name == "downgrade" for node in tree.body
        )
        if not has_downgrade:
            missing.append(path.name)
    assert missing == [], f"downgrade fonksiyonu eksik: {missing}"


def test_revision_ids_are_unique():
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for path in _migration_files():
        revision = _literal(path, "revision")
        if not revision:
            continue
        if revision in seen:
            duplicates.append(f"{revision}: {seen[revision]} ↔ {path.name}")
        else:
            seen[revision] = path.name
    assert duplicates == [], f"revision id çakışması: {duplicates}"


def test_new_migrations_do_not_duplicate_file_prefix():
    """Yeni migration dosya adı öneki çakışmamalı (bilinen istisnalar hariç)."""
    prefixes: dict[str, list[str]] = {}
    for path in _migration_files():
        match = re.match(r"^(\d{4})_", path.name)
        if match:
            prefixes.setdefault(match.group(1), []).append(path.name)
    unexpected = {
        prefix: names
        for prefix, names in prefixes.items()
        if len(names) > 1 and prefix not in KNOWN_DUPLICATE_FILE_PREFIXES
    }
    assert unexpected == {}, f"yeni dosya adı öneki çakışması: {unexpected}"


def test_down_revisions_resolve_or_are_known():
    revisions = {_literal(path, "revision") for path in _migration_files()}
    unresolved: list[str] = []
    for path in _migration_files():
        down = _literal(path, "down_revision")
        if down and down not in revisions:
            # 0072 gibi bilinen tarihsel boşluklar hariç tutulur.
            if any(known in path.name for known in KNOWN_MISSING_DOWN_REVISIONS):
                continue
            unresolved.append(f"{path.name} -> {down}")
    assert unresolved == [], f"çözülemeyen down_revision: {unresolved}"


def test_latest_change_request_migration_present():
    """Bu çalışmanın eklediği migration'lar mevcut ve bağlı olmalı."""
    by_revision = {
        _literal(path, "revision"): path.name
        for path in _migration_files()
        if _literal(path, "revision")
    }
    assert "0125" in by_revision, "audit user_agent migration eksik"
    assert "0126" in by_revision, "pro parity migration eksik"
    assert "0127" in by_revision, "change requests migration eksik"
    assert "0128" in by_revision, "risk Excel kaynak alanları migration eksik"
    assert _literal(VERSIONS / by_revision["0128"], "down_revision") == "0127"
    assert _literal(VERSIONS / by_revision["0127"], "down_revision") == "0126"
    assert _literal(VERSIONS / by_revision["0126"], "down_revision") == "0125"


def test_single_head_reported_by_alembic():
    """Alembic'in hesapladığı head sayısı 1 olmalı (çoklu head kazasını yakalar)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(VERSIONS.parent.parent / "alembic.ini"))
    config.set_main_option("script_location", str(VERSIONS.parent))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1, f"Çoklu alembic head tespit edildi: {heads}"


def _create_table_columns(source: str, table: str) -> set[str]:
    """Migration içindeki ``op.create_table("<table>", sa.Column("x", ...), ...)`` kolonlarını okur."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "create_table"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or node.args[0].value != table:
            continue
        columns: set[str] = set()
        for arg in node.args[1:]:
            if (
                isinstance(arg, ast.Call)
                and isinstance(arg.func, ast.Attribute)
                and arg.func.attr == "Column"
                and arg.args
                and isinstance(arg.args[0], ast.Constant)
            ):
                columns.add(str(arg.args[0].value))
        return columns
    return set()


def test_change_request_migration_matches_model():
    """0127 migration kolonları ORM modeliyle birebir aynı olmalı (parity guard)."""
    from app.models.entities import ChangeRequest, ChangeRequestEvent

    by_revision = {
        _literal(path, "revision"): path
        for path in _migration_files()
        if _literal(path, "revision")
    }
    source = _read_source(by_revision["0127"])

    assert _create_table_columns(source, "change_requests") == {
        column.name for column in ChangeRequest.__table__.columns
    }
    assert _create_table_columns(source, "change_request_events") == {
        column.name for column in ChangeRequestEvent.__table__.columns
    }
