import pytest
from backend.evidence.models import EvidenceReport, CorpusPresence

def test_evidence_report_creation():
    report = EvidenceReport(
        supported=True,
        presence=CorpusPresence.FOUND,
        reason="Checks passed",
        issues=[]
    )
    assert report.supported is True
    assert report.presence == CorpusPresence.FOUND
    assert report.reason == "Checks passed"
    assert report.issues == []

def test_evidence_report_defaults():
    report = EvidenceReport(
        supported=False,
        reason="",
        presence=CorpusPresence.NOT_FOUND,
        issues=[]
    )
    assert report.reason == ""

def test_evidence_report_immutable():
    report = EvidenceReport(
        supported=False,
        reason="",
        presence=CorpusPresence.NOT_FOUND,
        issues=[]
    )
    with pytest.raises(Exception):
        report.supported = True
