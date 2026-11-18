from app.core.contracts import EvidenceItem
from app.core.verification import validate_evidence, validate_verbatim_quote, classify_claim_support


def item(**kwargs):
    base = dict(evidence_id="e1", url="https://example.org/page", title="Example", retrieved_at="2026-10-20T00:00:00+00:00", open_status="opened", content_status="read", content="The official report states the project launched in 2024.", source_domain="example.org")
    base.update(kwargs)
    return EvidenceItem(**base)


def test_quote_must_be_verbatim():
    evidence = item()
    assert validate_verbatim_quote("The official report states the project launched in 2024.", evidence)
    assert not validate_verbatim_quote("The report says the project launched in 2024.", evidence)


def test_snippet_only_is_not_quote_eligible():
    evidence = item(open_status="failed", content_status="unavailable", content="", snippet="Some snippet")
    check = validate_evidence([evidence])[0]
    assert check["content_read"] is False
    assert check["quote_eligible"] is False


def test_claim_support_does_not_call_unread_metadata_supported():
    evidence = item(open_status="failed", content_status="unavailable", content="")
    result = classify_claim_support("The project launched in 2024", [evidence])
    assert result["support_status"] == "unsupported_no_read_content"


def test_research_answer_flags_unproven_url_and_quote():
    from app.core.verification import verify_research_answer
    evidence = item()
    report = verify_research_answer('The answer is "A quote not in the source text at all". See https://fabricated.example/page', 'Provide sources and a verbatim quote.', [evidence])
    assert 'answer_contains_url_without_input_or_retrieval_provenance' in report['warnings']
    assert 'requested_supporting_quote_missing_or_not_verbatim' in report['warnings']
    assert report['semantic_entailment_verified'] is False


def test_research_answer_requires_evidence_ids_and_warns_about_independence():
    from app.core.verification import verify_research_answer
    evidence = item()
    report = verify_research_answer('The project launched in 2024.', 'Provide sources and URLs.', [evidence])
    assert 'claim_evidence_mapping_missing' in report['warnings']
    assert 'independent_source_corroboration_not_established' in report['warnings']


def test_claim_evidence_mapping_is_explicitly_candidate_not_verified():
    from app.core.verification import verify_research_answer
    evidence = item(content='The official report states the project launched in 2024 and was led by the national research team.')
    report = verify_research_answer('The project launched in 2024 and was led by the national research team.', 'Research the project and provide sources.', [evidence])
    assert report['candidate_claim_evidence_mapping']
    assert report['candidate_claim_evidence_mapping'][0]['status'] == 'candidate_only_not_semantically_verified'
    assert report['semantic_entailment_verified'] is False
