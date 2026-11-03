"""Unit tests for PubMed XML normalization and source provenance."""
import xml.etree.ElementTree as ET

from usiphu import evidence


def test_pubmed_search_and_fetch_records_are_normalized(monkeypatch):
    search_xml = ET.fromstring("<eSearchResult><IdList><Id>12345</Id></IdList></eSearchResult>")
    article_xml = ET.fromstring("""
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>12345</PMID>
          <Article>
            <ArticleTitle>Clinical review of a pediatric condition</ArticleTitle>
            <Journal><Title>Example Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
            <Abstract><AbstractText>Evidence summary for clinical assessment.</AbstractText></Abstract>
            <PublicationTypeList><PublicationType>Systematic Review</PublicationType></PublicationTypeList>
          </Article>
        </MedlineCitation>
        <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/example</ArticleId></ArticleIdList></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """)
    calls = []

    def fake_request(url):
        calls.append(url)
        return search_xml if len(calls) == 1 else article_xml

    monkeypatch.setattr(evidence, "_request_xml", fake_request)
    records = evidence.retrieve_pubmed_evidence("pediatric clinical review", max_results=3)

    assert len(records) == 1
    assert records[0]["source_id"] == "PMID:12345"
    assert records[0]["source_url"] == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert records[0]["evidence_tier"] == "systematic_review_or_meta_analysis"
    assert records[0]["doi"] == "10.1000/example"
    assert "Evidence summary" in records[0]["abstract"]
    assert len(calls) == 2


def test_pubmed_rejects_invalid_query_and_result_count():
    import pytest

    with pytest.raises(ValueError):
        evidence.retrieve_pubmed_evidence("", 5)
    with pytest.raises(ValueError):
        evidence.retrieve_pubmed_evidence("kidney", 11)
