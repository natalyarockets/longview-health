"""Tests for storage/document_store -- document CRUD."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from longview_health.core.config import AppConfig
from longview_health.domain.enums import DocumentType
from longview_health.domain.models import Document
from longview_health.storage import document_store, vault_store


@pytest.fixture
def config(tmp_path: Path) -> AppConfig:
    return AppConfig(vault_root=tmp_path / "vaults")


@pytest.fixture
def vault(config: AppConfig) -> tuple[AppConfig, str]:
    vault_store.create_vault(config, "alice")
    return config, "alice"


def _make_doc(
    *,
    id: str = "doc001",
    filename: str = "labs.pdf",
    content_hash: str = "hash001",
) -> Document:
    return Document(
        id=id,
        vault_name="alice",
        filename=filename,
        file_path="/path/to/" + filename,
        document_type=DocumentType.PDF,
        content_hash=content_hash,
        ingested_at=datetime(2024, 3, 15, tzinfo=timezone.utc),
        page_count=2,
    )


class TestDocumentStore:
    def test_insert_and_get(self, vault: tuple) -> None:
        config, name = vault
        doc = _make_doc()
        document_store.insert_document(config, name, doc)

        got = document_store.get_document(config, name, "doc001")
        assert got is not None
        assert got.id == "doc001"
        assert got.filename == "labs.pdf"
        assert got.page_count == 2

    def test_get_nonexistent(self, vault: tuple) -> None:
        config, name = vault
        assert document_store.get_document(config, name, "nope") is None

    def test_get_by_hash(self, vault: tuple) -> None:
        config, name = vault
        doc = _make_doc()
        document_store.insert_document(config, name, doc)

        got = document_store.get_document_by_hash(config, name, "hash001")
        assert got is not None
        assert got.id == "doc001"

    def test_get_by_hash_not_found(self, vault: tuple) -> None:
        config, name = vault
        assert document_store.get_document_by_hash(config, name, "nope") is None

    def test_list_documents(self, vault: tuple) -> None:
        config, name = vault
        document_store.insert_document(config, name, _make_doc(id="d1", filename="a.pdf"))
        document_store.insert_document(config, name, _make_doc(id="d2", filename="b.pdf"))

        docs = document_store.list_documents(config, name)
        assert len(docs) == 2
        assert docs[0].filename == "a.pdf"
        assert docs[1].filename == "b.pdf"

    def test_document_count(self, vault: tuple) -> None:
        config, name = vault
        assert document_store.document_count(config, name) == 0

        document_store.insert_document(config, name, _make_doc())
        assert document_store.document_count(config, name) == 1

    def test_upsert_replaces(self, vault: tuple) -> None:
        config, name = vault
        document_store.insert_document(config, name, _make_doc(id="d1", filename="old.pdf"))
        document_store.insert_document(config, name, _make_doc(id="d1", filename="new.pdf"))

        docs = document_store.list_documents(config, name)
        assert len(docs) == 1
        assert docs[0].filename == "new.pdf"
