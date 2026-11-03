"""PubMed evidence retrieval with source metadata for draft card authoring."""
from __future__ import annotations

import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class EvidenceRetrievalError(RuntimeError):
    """Raised when PubMed cannot provide a usable evidence packet."""


def _request_xml(url: str) -> ET.Element:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UsiphuMedicalLearning/2.0 (educational evidence retrieval)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return ET.fromstring(response.read())
    except Exception as exc:
        raise EvidenceRetrievalError(f"PubMed request failed: {exc}") from exc


def _text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(part.strip() for part in node.itertext() if part.strip())


def _publication_date(article: ET.Element) -> str:
    for path in (".//PubDate", ".//DateCompleted", ".//DateRevised"):
        node = article.find(path)
        if node is None:
            continue
        year = _text(node.find("Year"))
        month = _text(node.find("Month"))
        day = _text(node.find("Day"))
        medline = _text(node.find("MedlineDate"))
        if year:
            return "-".join(part for part in (year, month, day) if part)
        if medline:
            return medline
    return "date not supplied by PubMed"


def _evidence_tier(publication_types: list[str]) -> tuple[str, int]:
    text = " ".join(publication_types).casefold()
    if any(term in text for term in ("practice guideline", "guideline", "consensus")):
        return "guideline_or_consensus", 1
    if any(term in text for term in ("systematic review", "meta-analysis")):
        return "systematic_review_or_meta_analysis", 2
    if "randomized controlled trial" in text:
        return "randomized_trial", 3
    if "review" in text:
        return "review", 4
    return "primary_or_other_study", 5


def _publication_year(value: str) -> int:
    match = re.search(r"\b(19|20)\d{2}\b", value)
    return int(match.group(0)) if match else 0


def retrieve_pubmed_evidence(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Retrieve up to ten PubMed records; return abstracts and stable PMID links."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1200:
        raise ValueError("Evidence query must contain 1–1200 characters")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be between 1 and 10")

    params = {
        "db": "pubmed",
        "term": query.strip(),
        "retmax": str(max_results),
        "retmode": "xml",
        "sort": "relevance",
        "tool": "usiphu",
    }
    email = os.getenv("NCBI_EMAIL")
    if email:
        params["email"] = email
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    search_url = EUTILS + "/esearch.fcgi?" + urllib.parse.urlencode(params)
    search_root = _request_xml(search_url)
    pmids = [node.text for node in search_root.findall(".//IdList/Id") if node.text]
    if not pmids:
        return []

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    fetch_url = EUTILS + "/efetch.fcgi?" + urllib.parse.urlencode(fetch_params)
    root = _request_xml(fetch_url)
    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _text(article.find(".//PMID"))
        title = _text(article.find(".//ArticleTitle"))
        abstract_parts = [
            _text(node) for node in article.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(part for part in abstract_parts if part)
        if not pmid or not title or not abstract:
            continue
        journal = _text(article.find(".//Journal/Title"))
        publication_types = [
            _text(node) for node in article.findall(".//PublicationTypeList/PublicationType")
        ]
        doi = ""
        for identifier in article.findall(".//ArticleId"):
            if identifier.attrib.get("IdType") == "doi":
                doi = _text(identifier)
                break
        evidence_tier, evidence_rank = _evidence_tier(publication_types)
        records.append({
            "source_id": f"PMID:{pmid}",
            "source_title": title,
            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source_date": _publication_date(article),
            "journal": journal,
            "doi": doi or None,
            "publication_types": publication_types,
            "evidence_tier": evidence_tier,
            "evidence_rank": evidence_rank,
            "abstract": abstract[:9000],
            "retrieved_at": date.today().isoformat(),
            "source_database": "PubMed",
            "limitations": (
                "Abstract-level evidence only; verify full text, methods, population, "
                "publication status, guideline currency, and applicability before approval."
            ),
        })
    # Prefer guideline/systematic-review publication types, then newer records.
    records.sort(
        key=lambda item: (item["evidence_rank"], -_publication_year(item["source_date"]))
    )
    return records
