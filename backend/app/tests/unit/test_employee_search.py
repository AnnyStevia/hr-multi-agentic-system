"""Unit: multi-word employee name search."""

from __future__ import annotations

from app.modules.employees.repository import _employee_search_clause


def test_employee_search_clause_builds_for_full_name():
    clause = _employee_search_clause("Prince Nkoulou")
    assert clause is not None


def test_employee_search_clause_empty():
    assert _employee_search_clause("   ") is None
