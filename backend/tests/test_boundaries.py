"""Package boundaries: the domain and the agent are libraries the API service depends on, never the
other way round. The agent reaches the DB only through `onboarding_core.ports`."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGES = Path(__file__).resolve().parents[1] / "packages"

FORBIDDEN = {
    "core": {"app", "onboarding_agent", "sqlalchemy", "fastapi", "langgraph", "langchain_core", "httpx"},
    "agent": {"app", "sqlalchemy", "fastapi"},
}


def imported_roots(path: Path) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_imports_stay_inside_its_boundary(package):
    sources = sorted((PACKAGES / package / "src").rglob("*.py"))
    assert sources
    violations = {
        str(path.relative_to(PACKAGES)): sorted(imported_roots(path) & FORBIDDEN[package]) for path in sources
    }
    assert {k: v for k, v in violations.items() if v} == {}
