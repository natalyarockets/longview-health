"""Tests for storage/review_store -- review queue persistence."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from longview_health.core.config import AppConfig
from longview_health.domain.enums import DocumentType
from longview_health.domain.models import Document
from longview_health.storage import document_store, review_store, vault_store


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(vault_root=tmp_path / "vaults")


@pytest.fixture
def vault(config: AppConfig) -> tuple[AppConfig, str]:
    vault_store.create_vault(config, "alice")
    # Insert a document (FK target)
    doc = Document(
        id="doc001",
        vault_name="alice",
        filename="labs.pdf",
        file_path="/path/labs.pdf",
        document_type=DocumentType.PDF,
        content_hash="hash001",
        ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    document_store.insert_document(config, "alice", doc)
    return config, "alice"


class TestReviewStore:
    def test_add_and_list_pending(self, vault: tuple) -> None:
        config, name = vault
        review_store.add_to_review(
            config, name,
            result_id="r001", document_id="doc001",
            test_name="HDL", reason="Unrecognized unit",
        )

        items = review_store.list_pending(config, name)
        assert len(items) == 1
        assert items[0].test_name == "HDL"
        assert items[0].reason == "Unrecognized unit"
        assert items[0].resolved is False

    def test_resolve_item(self, vault: tuple) -> None:
        config, name = vault
        review_store.add_to_review(
            config, name,
            result_id="r001", document_id="doc001",
            test_name="HDL", reason="Flagged",
        )

        items = review_store.list_pending(config, name)
        assert len(items) == 1

        resolved = review_store.resolve_item(config, name, items[0].id)
        assert resolved is True

        assert review_store.list_pending(config, name) == []

    def test_resolve_nonexistent(self, vault: tuple) -> None:
        config, name = vault
        assert review_store.resolve_item(config, name, "nope") is False

    def test_list_all_includes_resolved(self, vault: tuple) -> None:
        config, name = vault
        review_store.add_to_review(
            config, name,
            result_id="r001", document_id="doc001",
            test_name="HDL", reason="Flagged",
        )
        items = review_store.list_pending(config, name)
        review_store.resolve_item(config, name, items[0].id)

        all_items = review_store.list_all(config, name)
        assert len(all_items) == 1
        assert all_items[0].resolved is True

    def test_pending_count(self, vault: tuple) -> None:
        config, name = vault
        assert review_store.pending_count(config, name) == 0

        review_store.add_to_review(
            config, name,
            result_id="r001", document_id="doc001",
            test_name="HDL", reason="Flagged",
        )
        assert review_store.pending_count(config, name) == 1

    def test_multiple_items(self, vault: tuple) -> None:
        config, name = vault
        review_store.add_to_review(
            config, name,
            result_id="r001", document_id="doc001",
            test_name="HDL", reason="Issue 1",
        )
        review_store.add_to_review(
            config, name,
            result_id="r002", document_id="doc001",
            test_name="LDL", reason="Issue 2",
        )

        items = review_store.list_pending(config, name)
        assert len(items) == 2
        assert review_store.pending_count(config, name) == 2
