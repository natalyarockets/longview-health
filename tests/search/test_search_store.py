"""Tests for storage/search_store -- FTS5 operations."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from longview_health.core.config import AppConfig
from longview_health.domain.enums import DocumentType
from longview_health.domain.models import Document
from longview_health.storage import document_store, search_store, vault_store


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(vault_root=tmp_path / "vaults")


@pytest.fixture
def vault(config: AppConfig) -> tuple[AppConfig, str]:
    vault_store.create_vault(config, "alice")
    # Insert a document (FK target for search results context)
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


class TestSearchStore:
    def test_index_and_search(self, vault: tuple) -> None:
        config, name = vault
        search_store.index_document(
            config, name, "doc001", "HDL Cholesterol 55 mg/dL normal range 40-60"
        )

        hits = search_store.search(config, name, "cholesterol")
        assert len(hits) == 1
        assert hits[0].document_id == "doc001"
        assert "cholesterol" in hits[0].snippet.lower()

    def test_no_results(self, vault: tuple) -> None:
        config, name = vault
        search_store.index_document(config, name, "doc001", "blood pressure 120/80")

        hits = search_store.search(config, name, "cholesterol")
        assert hits == []

    def test_multiple_documents(self, vault: tuple) -> None:
        config, name = vault
        # Add second document
        doc2 = Document(
            id="doc002",
            vault_name="alice",
            filename="imaging.pdf",
            file_path="/path/imaging.pdf",
            document_type=DocumentType.PDF,
            content_hash="hash002",
            ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        document_store.insert_document(config, name, doc2)

        search_store.index_document(config, name, "doc001", "HDL Cholesterol results")
        search_store.index_document(config, name, "doc002", "MRI Brain no acute findings")

        hits = search_store.search(config, name, "brain")
        assert len(hits) == 1
        assert hits[0].document_id == "doc002"

    def test_reindex_replaces(self, vault: tuple) -> None:
        config, name = vault
        search_store.index_document(config, name, "doc001", "old content")
        search_store.index_document(config, name, "doc001", "new content entirely")

        assert search_store.search(config, name, "old") == []
        assert len(search_store.search(config, name, "new")) == 1

    def test_document_indexed(self, vault: tuple) -> None:
        config, name = vault
        assert not search_store.document_indexed(config, name, "doc001")

        search_store.index_document(config, name, "doc001", "some text")
        assert search_store.document_indexed(config, name, "doc001")

    def test_limit(self, vault: tuple) -> None:
        config, name = vault
        search_store.index_document(config, name, "doc001", "cholesterol test results")

        hits = search_store.search(config, name, "cholesterol", limit=0)
        assert hits == []

    def test_phrase_search(self, vault: tuple) -> None:
        config, name = vault
        search_store.index_document(
            config, name, "doc001", "HDL Cholesterol 55 mg/dL LDL Cholesterol 120 mg/dL"
        )

        hits = search_store.search(config, name, '"HDL Cholesterol"')
        assert len(hits) == 1
