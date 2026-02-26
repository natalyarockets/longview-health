"""Tests for deterministic identifier generation."""

from datetime import date
from pathlib import Path

from longview_health.domain.identifiers import content_hash, result_key


def test_content_hash_deterministic(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = content_hash(f)
    h2 = content_hash(f)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_content_hash_differs_for_different_content(tmp_path: Path) -> None:
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello")
    f2.write_text("world")
    assert content_hash(f1) != content_hash(f2)


def test_result_key_deterministic() -> None:
    k1 = result_key("doc123", "HDL", date(2024, 1, 15))
    k2 = result_key("doc123", "HDL", date(2024, 1, 15))
    assert k1 == k2
    assert len(k1) == 16


def test_result_key_differs_for_different_inputs() -> None:
    k1 = result_key("doc123", "HDL", date(2024, 1, 15))
    k2 = result_key("doc123", "LDL", date(2024, 1, 15))
    k3 = result_key("doc123", "HDL", date(2024, 2, 15))
    assert k1 != k2
    assert k1 != k3
