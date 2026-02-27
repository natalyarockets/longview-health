"""Search indexer -- populate FTS5 from parsed document text.

Called during ingestion to index each document's full text content
for full-text search.
"""

from longview_health.core.config import AppConfig
from longview_health.domain.models import ParsedDocument
from longview_health.storage import search_store


def index_parsed_document(
    config: AppConfig, vault_name: str, parsed: ParsedDocument
) -> None:
    """Index a parsed document's text content for FTS search.

    Uses the markdown representation as the primary content, since it
    includes both text blocks and table content in a searchable form.
    """
    search_store.index_document(
        config, vault_name, parsed.document_id, parsed.markdown
    )
