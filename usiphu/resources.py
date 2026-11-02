"""Responsible outbound discovery links for medical learning resources."""
from __future__ import annotations
from urllib.parse import quote_plus

RESOURCE_PROVIDERS = [
    {"id": "pubmed", "name": "PubMed", "kind": "literature_index", "base": "https://pubmed.ncbi.nlm.nih.gov/?term=", "note": "Bibliographic search; full text is not guaranteed."},
    {"id": "pmc", "name": "PubMed Central", "kind": "open_full_text", "base": "https://pmc.ncbi.nlm.nih.gov/?term=", "note": "Free full-text archive; check article license."},
    {"id": "cureus", "name": "Cureus", "kind": "open_access_journal", "base": "https://www.cureus.com/search?query=", "note": "Open-access journal; assess article quality and relevance."},
    {"id": "ankiweb", "name": "AnkiWeb shared decks", "kind": "flashcard_discovery", "base": "https://ankiweb.net/shared/decks?search=", "note": "Third-party decks; verify accuracy, date, and license before use."},
    {"id": "doctorde", "name": "DoctorDE", "kind": "exam_practice", "base": "https://www.google.com/search?q=", "note": "Search route only; verify the current official site and content before relying on it."},
    {"id": "who", "name": "WHO publications", "kind": "guidelines", "base": "https://www.who.int/publications/i?search=", "note": "Global guidance; local protocols may differ."},
    {"id": "nice", "name": "NICE guidance", "kind": "guidelines", "base": "https://www.nice.org.uk/search?q=", "note": "UK guidance; check jurisdiction and update date."},
    {"id": "cochrane", "name": "Cochrane Library", "kind": "evidence_synthesis", "base": "https://www.cochranelibrary.com/search?searchBy=0&searchText=", "note": "Systematic reviews; check currency and applicability."},
]


def discover_resources(topic: str, specialty: str | None = None) -> list[dict[str, str]]:
    query = " ".join(part for part in (specialty, topic) if part).strip()
    encoded = quote_plus(query)
    return [{**provider, "url": provider["base"] + encoded} for provider in RESOURCE_PROVIDERS]
