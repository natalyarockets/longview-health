"""Result merger -- deduplicates results from multiple extractors.

When multiple extractors produce results for the same test (e.g., a table
extractor and an LLM extractor both find "WBC"), this module keeps only
the highest-priority version. Priority: table-v1 > form-v1 > llm-v1.
"""

from __future__ import annotations

from longview_health.domain.models import MedicalResult

# Lower number = higher priority
_EXTRACTOR_PRIORITY: dict[str, int] = {
    "table-v1": 0,
    "form-v1": 1,
    "llm-v1": 2,
}


def _priority(result: MedicalResult) -> int:
    return _EXTRACTOR_PRIORITY.get(result.extractor_version, 99)


def merge(*result_lists: list[MedicalResult]) -> list[MedicalResult]:
    """Merge results from multiple extractors, deduplicating by result ID.

    When multiple results share the same ID (same document + test + date),
    the one from the highest-priority extractor wins.

    Args:
        *result_lists: Variable number of result lists to merge.

    Returns:
        Deduplicated list of MedicalResult objects.
    """
    best: dict[str, MedicalResult] = {}

    for results in result_lists:
        for result in results:
            existing = best.get(result.id)
            if existing is None or _priority(result) < _priority(existing):
                best[result.id] = result

    return list(best.values())
