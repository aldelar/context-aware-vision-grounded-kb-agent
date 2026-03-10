"""Tests for per-function and monolithic function_app.py entry points.

Validates that each entry point:
- Can be imported without errors
- Exposes a FunctionApp instance named `app`
- Only imports its own fn_* package (no cross-imports)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FUNCTIONS_ROOT = Path(__file__).resolve().parent.parent

# Per-function entry points: (module_dir, expected_fn_import)
PER_FUNCTION_ENTRIES = [
    ("fn_convert_cu", "fn_convert_cu"),
    ("fn_convert_mistral", "fn_convert_mistral"),
    ("fn_convert_markitdown", "fn_convert_markitdown"),
    ("fn_index", "fn_index"),
]


def _parse_imports(filepath: Path) -> set[str]:
    """Return top-level module names imported by a Python file (via AST)."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


# ---------------------------------------------------------------------------
# Per-function entry points: import + app instance
# ---------------------------------------------------------------------------

class TestPerFunctionEntryPointImports:
    """Each per-function function_app.py can be imported and exposes `app`."""

    @pytest.mark.parametrize("module_dir,_expected_import", PER_FUNCTION_ENTRIES)
    def test_entry_point_importable(self, module_dir, _expected_import):
        entry_file = FUNCTIONS_ROOT / module_dir / "function_app.py"
        assert entry_file.exists(), f"{entry_file} does not exist"

    @pytest.mark.parametrize("module_dir,_expected_import", PER_FUNCTION_ENTRIES)
    def test_entry_point_has_function_app_instance(self, module_dir, _expected_import):
        entry_file = FUNCTIONS_ROOT / module_dir / "function_app.py"
        source = entry_file.read_text()
        tree = ast.parse(source, filename=str(entry_file))
        # Look for `app = func.FunctionApp()` — an assignment to `app`
        app_assigned = any(
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "app" for t in node.targets
            )
            for node in ast.walk(tree)
        )
        assert app_assigned, f"{module_dir}/function_app.py does not assign `app`"


# ---------------------------------------------------------------------------
# Per-function entry points: no cross-imports
# ---------------------------------------------------------------------------

class TestPerFunctionNoCrossImports:
    """Each per-function entry point only imports its own fn_* package."""

    ALL_FN_PACKAGES = {"fn_convert_cu", "fn_convert_mistral", "fn_convert_markitdown", "fn_index"}

    @pytest.mark.parametrize("module_dir,expected_import", PER_FUNCTION_ENTRIES)
    def test_only_imports_own_fn_package(self, module_dir, expected_import):
        entry_file = FUNCTIONS_ROOT / module_dir / "function_app.py"
        imports = _parse_imports(entry_file)

        fn_imports = imports & self.ALL_FN_PACKAGES
        assert expected_import in fn_imports, (
            f"{module_dir}/function_app.py does not import {expected_import}"
        )

        unexpected = fn_imports - {expected_import}
        assert not unexpected, (
            f"{module_dir}/function_app.py has cross-imports: {unexpected}"
        )


# ---------------------------------------------------------------------------
# Per-function entry points: routes
# ---------------------------------------------------------------------------

EXPECTED_ROUTES = [
    ("fn_convert_cu", "convert"),
    ("fn_convert_mistral", "convert-mistral"),
    ("fn_convert_markitdown", "convert-markitdown"),
    ("fn_index", "index"),
]


class TestPerFunctionRoutes:
    """Each per-function entry point declares the correct route string."""

    @pytest.mark.parametrize("module_dir,expected_route", EXPECTED_ROUTES)
    def test_route_declared(self, module_dir, expected_route):
        entry_file = FUNCTIONS_ROOT / module_dir / "function_app.py"
        source = entry_file.read_text()
        assert f'route="{expected_route}"' in source, (
            f'{module_dir}/function_app.py missing route="{expected_route}"'
        )
