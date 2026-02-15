"""Cross-system search -- the unique value Praxis provides.

Searches across Lineage journal, patterns, graph, and Lore registry,
returning scored results from a single query.
"""

from . import store
from . import registry


def _score_match(query_lower: str, text: str) -> float:
    """Simple relevance score: exact match > word match > substring."""
    text_lower = text.lower()
    if query_lower == text_lower:
        return 1.0
    words = query_lower.split()
    word_hits = sum(1 for w in words if w in text_lower)
    if word_hits == len(words):
        return 0.9
    if word_hits > 0:
        return 0.5 * (word_hits / len(words))
    if query_lower in text_lower:
        return 0.3
    return 0.0


def _text_of(data: dict) -> str:
    """Flatten a dict into searchable text."""
    parts = []
    for v in data.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.append(_text_of(item))
        elif isinstance(v, dict):
            parts.append(_text_of(v))
    return " ".join(parts)


def search_journal(query: str) -> list[dict]:
    """Search Lineage journal entries."""
    query_lower = query.lower()
    results = []
    for entry in store.read_journal():
        if "_parse_error" in entry:
            continue
        text = _text_of(entry)
        score = _score_match(query_lower, text)
        if score > 0:
            results.append({
                "source": "journal",
                "relevance": score,
                "id": entry.get("id", ""),
                "summary": entry.get("decision", "")[:120],
                "data": entry,
            })
    return results


def search_patterns(query: str) -> list[dict]:
    """Search Lineage patterns."""
    query_lower = query.lower()
    results = []
    for pat in store.read_patterns():
        if not isinstance(pat, dict):
            continue
        text = _text_of(pat)
        score = _score_match(query_lower, text)
        if score > 0:
            results.append({
                "source": "pattern",
                "relevance": score,
                "id": pat.get("id", ""),
                "summary": pat.get("name", "")[:120],
                "data": pat,
            })
    return results


def search_graph(query: str) -> list[dict]:
    """Search Lineage knowledge graph nodes."""
    query_lower = query.lower()
    results = []
    graph = store.read_graph()
    nodes = graph.get("nodes", {})
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        text = _text_of(node)
        score = _score_match(query_lower, text)
        if score > 0:
            results.append({
                "source": "graph",
                "relevance": score,
                "id": node_id,
                "summary": node.get("name", node_id)[:120],
                "data": node,
            })
    return results


def search_registry(query: str) -> list[dict]:
    """Search Lore registry projects."""
    query_lower = query.lower()
    results = []
    for project_name in registry.list_projects():
        info = registry.show(project_name)
        text = _text_of(info)
        score = _score_match(query_lower, text)
        if score > 0:
            results.append({
                "source": "registry",
                "relevance": score,
                "id": project_name,
                "summary": project_name,
                "data": info,
            })
    return results


def search(query: str) -> list[dict]:
    """Search across Lineage journal, patterns, graph, and Lore registry."""
    results = []
    results += search_journal(query)
    results += search_patterns(query)
    results += search_graph(query)
    results += search_registry(query)
    return sorted(results, key=lambda r: r["relevance"], reverse=True)
