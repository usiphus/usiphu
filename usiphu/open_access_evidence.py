"""Open-access medical full-text retrieval via Europe PMC.

Only records explicitly marked open access are returned. Full text is preferred;
abstract-only records are labelled and must not be treated as full-text evidence.
Retrieved text is transient review input and is not written to the question bank.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_USER_AGENT = "USIPHU/2.0 (open-access medical education evidence review)"
_STOP_WORDS = {
    "about", "after", "against", "among", "and", "are", "best", "between",
    "case", "compared", "consider", "does", "during", "each", "from", "has",
    "have", "how", "into", "most", "other", "patient", "patients", "should",
    "that", "their", "there", "these", "this", "those", "through", "under",
    "using", "what", "when", "which", "with", "would", "following", "common",
    "management", "diagnosis", "treatment", "year", "years", "old", "boy", "girl",
    "man", "woman", "male", "female", "presents", "presented", "presenting",
    "history", "showing", "shows", "without", "normal", "abnormal",
}


class OpenAccessEvidenceError(RuntimeError):
    """Raised when Europe PMC cannot be reached or returns invalid data."""


def _request(url: str, *, json_response: bool = False) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = response.read()
        if json_response:
            import json
            return json.loads(payload.decode("utf-8"))
        return ET.fromstring(payload)
    except Exception as exc:
        raise OpenAccessEvidenceError(f"Open-access evidence retrieval failed: {exc}") from exc


def _plain_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", " ".join(part.strip() for part in node.itertext() if part.strip())).strip()


def _search_terms(candidate: dict[str, Any]) -> list[str]:
    stem = str(candidate.get("stem_extracted") or "")
    option_text = " ".join(
        str(item.get("text", "")) for item in candidate.get("options", [])
        if isinstance(item, dict)
    )
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", (stem + " " + option_text).casefold())
    generic = _STOP_WORDS | {
        "method", "methods", "improves", "improved", "improvement", "diagnostic",
        "assessment", "test", "tests", "likely", "associated", "performed",
        "indicated", "indication", "cause", "causes", "caused", "feature",
        "features", "following", "option", "options", "treatment", "management",
    }
    terms: list[str] = []
    for word in words:
        if word not in generic and word not in terms:
            terms.append(word)
    for extra in (candidate.get("specialty_label"), candidate.get("topic_id")):
        for word in re.findall(r"[A-Za-z][A-Za-z-]{2,}", str(extra or "").casefold()):
            if word not in generic and word not in terms:
                terms.append(word)
    return terms[:10]

def _license(article: ET.Element) -> str:
    for node in article.findall(".//permissions/license"):
        href = next((value for key, value in node.attrib.items() if key.endswith("}href") or key == "href"), "")
        label = _plain_text(node)
        return " ".join(part for part in (label, href) if part)[:500]
    return "Open-access status reported by Europe PMC; specific licence not exposed in article XML."


def _full_text(article: ET.Element) -> str:
    body = article.find(".//body")
    if body is None:
        return ""
    parent = {child: node for node in body.iter() for child in node}
    excluded = {"ref-list", "fig", "table-wrap", "supplementary-material"}
    important = ("result", "discussion", "conclusion", "recommendation", "clinical implication")
    paragraphs: list[tuple[int, str]] = []
    for section in body.iter():
        if section.tag.rsplit("}", 1)[-1].casefold() != "p":
            continue
        ancestor = parent.get(section)
        skip = False
        section_titles: list[str] = []
        while ancestor is not None and ancestor is not body:
            tag = ancestor.tag.rsplit("}", 1)[-1].casefold()
            if tag in excluded:
                skip = True
                break
            if tag == "sec":
                title = _plain_text(ancestor.find("./title"))
                if title:
                    section_titles.append(title)
            ancestor = parent.get(ancestor)
        if skip:
            continue
        value = _plain_text(section)
        if value:
            section_label = " / ".join(reversed(section_titles))
            priority = 0 if any(term in section_label.casefold() for term in important) else 1
            paragraphs.append((priority, f"[{section_label}] {value}" if section_label else value))
    paragraphs.sort(key=lambda item: item[0])
    unique: list[str] = []
    seen: set[str] = set()
    for _, paragraph in paragraphs:
        if paragraph not in seen:
            seen.add(paragraph)
            unique.append(paragraph)
    return "\n".join(unique)[:9000]

def retrieve_open_access_evidence(
    candidate: dict[str, Any], *, max_results: int = 4
) -> list[dict[str, Any]]:
    """Search Europe PMC and return up to four open-access medical sources."""
    if not 1 <= max_results <= 6:
        raise ValueError("max_results must be between 1 and 6")
    terms = _search_terms(candidate)
    if len(terms) < 2:
        return []
    expression = " OR ".join(terms)
    query = f"OPEN_ACCESS:Y AND TITLE_ABS:({expression})"
    params = urllib.parse.urlencode({
        "query": query,
        "format": "json",
        "pageSize": str(max_results * 5),
        "resultType": "core",
        "sort": "RELEVANCE",
    })
    search_url = f"{EUROPE_PMC}/search?{params}"
    payload = _request(search_url, json_response=True)
    results = payload.get("resultList", {}).get("result", [])
    if not isinstance(results, list):
        raise OpenAccessEvidenceError("Europe PMC returned an invalid result list.")

    ranked_results = []
    for item in results:
        if str(item.get("isOpenAccess", "")).upper() != "Y" or not item.get("pmcid"):
            continue
        searchable = " ".join((str(item.get("title") or ""), str(item.get("abstractText") or ""))).casefold()
        score = sum(1 for term in terms if term in searchable)
        ranked_results.append((score, item))
    ranked_results.sort(key=lambda pair: pair[0], reverse=True)

    records: list[dict[str, Any]] = []
    for score, item in ranked_results:
        if score == 0:
            continue
        if str(item.get("isOpenAccess", "")).upper() != "Y":
            continue
        pmcid = str(item.get("pmcid") or "").strip()
        if not pmcid:
            continue
        full_url = f"{EUROPE_PMC}/{urllib.parse.quote(pmcid)}/fullTextXML"
        article = _request(full_url)
        abstract = _plain_text(article.find(".//abstract"))
        body_text = _full_text(article)
        evidence_text = (
            ("ABSTRACT: " + abstract + "\nFULL TEXT EXCERPTS:\n" + body_text)
            if body_text else abstract
        )
        if not evidence_text:
            continue
        title = _plain_text(article.find(".//article-title")) or str(item.get("title") or "")
        doi = str(item.get("doi") or "").strip() or None
        pmid = str(item.get("pmid") or "").strip() or None
        records.append({
            "source_id": f"PMC:{pmcid}",
            "source_title": title,
            "source_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
            "source_date": str(item.get("firstPublicationDate") or item.get("pubYear") or "date not supplied"),
            "journal": str(item.get("journalTitle") or ""),
            "doi": doi,
            "pmid": pmid,
            "pmcid": pmcid,
            "license": _license(article),
            "is_open_access": True,
            "full_text_available": bool(body_text),
            "evidence_text": evidence_text,
            "abstract": abstract[:2500],
            "retrieved_at": date.today().isoformat(),
            "source_database": "Europe PMC / PubMed Central",
            "limitations": (
                "Open-access article text retrieved for educational review. Check study design, "
                "population, methods, publication status, date, and applicability; this is not "
                "a substitute for current specialty guidelines or local protocols."
            ),
        })
        if len(records) >= max_results:
            break
    return records
