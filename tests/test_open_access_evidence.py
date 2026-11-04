"""Tests for Europe PMC open-access full-text retrieval."""
from usiphu import open_access_evidence as evidence


def test_retrieves_only_open_access_pmc_full_text(monkeypatch):
    calls = []

    def fake_request(url, *, json_response=False):
        calls.append((url, json_response))
        if json_response:
            return {
                "resultList": {"result": [
                    {"isOpenAccess": "N", "pmcid": "PMC000"},
                    {"isOpenAccess": "Y", "pmcid": "PMC123", "title": "Clinical study",
                     "firstPublicationDate": "2024-03-01", "journalTitle": "Example Journal",
                     "doi": "10.1000/example", "pmid": "12345"},
                ]}
            }
        return evidence.ET.fromstring("""
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <front><article-meta>
            <title-group><article-title>Clinical study</article-title></title-group>
            <permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</license></permissions>
            <abstract><p>Study abstract text.</p></abstract>
          </article-meta></front>
          <body><sec><title>Results</title><p>Computed tomography improved diagnostic assessment in this cohort.</p></sec></body>
        </article>
        """)

    monkeypatch.setattr(evidence, "_request", fake_request)
    records = evidence.retrieve_open_access_evidence({
        "stem_extracted": "Which imaging method improves diagnostic assessment?",
        "specialty_label": "Radiology",
    })

    assert len(records) == 1
    assert records[0]["source_id"] == "PMC:PMC123"
    assert records[0]["is_open_access"] is True
    assert records[0]["full_text_available"] is True
    assert "Computed tomography" in records[0]["evidence_text"]
    assert records[0]["license"].startswith("CC BY 4.0")
    assert records[0]["source_url"] == "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/"
    assert len(calls) == 2


def test_returns_no_sources_when_question_has_too_few_search_terms():
    assert evidence.retrieve_open_access_evidence({"stem_extracted": "What is it?"}) == []


def test_validates_result_limit():
    import pytest

    with pytest.raises(ValueError):
        evidence.retrieve_open_access_evidence({"stem_extracted": "kidney disease treatment"}, max_results=0)


def test_abstract_is_used_when_open_access_full_text_body_missing(monkeypatch):
    def fake_request(url, *, json_response=False):
        if json_response:
            return {"resultList": {"result": [
                {"isOpenAccess": "Y", "pmcid": "PMC456", "title": "Abstract-only article"}
            ]}}
        return evidence.ET.fromstring("""
        <article><front><article-meta>
          <title-group><article-title>Abstract-only article</article-title></title-group>
          <abstract><p>Open access abstract text is available.</p></abstract>
        </article-meta></front></article>
        """)

    monkeypatch.setattr(evidence, "_request", fake_request)
    records = evidence.retrieve_open_access_evidence({"stem_extracted": "acute kidney injury management"})
    assert len(records) == 1
    assert records[0]["full_text_available"] is False
    assert "abstract text" in records[0]["evidence_text"]
