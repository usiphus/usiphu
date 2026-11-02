"""Responsible outbound discovery links; no third-party content is copied."""
from urllib.parse import quote_plus

PROVIDERS = [
    ("pubmed", "PubMed", "Literature index", "https://pubmed.ncbi.nlm.nih.gov/?term=", "Full text is not guaranteed."),
    ("pmc", "PubMed Central", "Open full text", "https://pmc.ncbi.nlm.nih.gov/?term=", "Check each article's license."),
    ("cureus", "Cureus", "Open-access journal", "https://www.cureus.com/search?query=", "Assess methods, peer review, and relevance."),
    ("ankiweb", "AnkiWeb shared decks", "Flashcard discovery", "https://ankiweb.net/shared/decks?search=", "Third-party decks; verify accuracy and redistribution terms."),
    ("doctorde", "DoctorDE (search)", "Exam-practice discovery", "https://www.google.com/search?q=", "Search route pending verification of a stable official endpoint."),
    ("who", "WHO publications", "Guidelines", "https://www.who.int/publications/i?search=", "Check country applicability and publication date."),
    ("nice", "NICE guidance", "Guidelines", "https://www.nice.org.uk/search?q=", "UK guidance; local protocols may differ."),
    ("cochrane", "Cochrane Library", "Evidence synthesis", "https://www.cochranelibrary.com/search?searchBy=0&searchText=", "Check review currency and population applicability."),
]


def discover_resources(topic: str, specialty: str | None = None) -> list[dict[str, str]]:
    query = " ".join(part for part in (specialty, topic) if part).strip()
    encoded = quote_plus(query)
    return [{"id": pid, "name": name, "kind": kind, "url": base + encoded, "note": note}
            for pid, name, kind, base, note in PROVIDERS]
