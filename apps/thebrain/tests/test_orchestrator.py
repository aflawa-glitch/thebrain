from types import SimpleNamespace
import asyncio
from app.core.contracts import RequestContext
import app.core.orchestrator as orchestrator


def test_central_lifecycle_uses_registered_capability_and_trace(isolated_database, monkeypatch):
    async def fake_chat(messages, **kwargs):
        return "Jawaban teruji dari mock model."
    mock_llm = SimpleNamespace(chat=fake_chat)
    monkeypatch.setattr(orchestrator, "for_role", lambda role: mock_llm)
    context = RequestContext(conversation_id="test-conversation")
    result = asyncio.run(orchestrator.run_request("Bantu gue mikir", context))
    assert result["status"] == "completed"
    assert result["route"] == "chat"
    stages = [event["stage"] for event in result["events"]]
    assert stages[0] == "interpret" and "plan" in stages and "verify" in stages and "explain" in stages
    assert "capability:chat_response" in stages
    assert result["trace_id"] == context.trace_id


def test_model_tokens_flow_to_stream_queue(isolated_database, monkeypatch):
    async def fake_chat_stream(messages, on_chunk, **kwargs):
        await on_chunk("partial ")
        await on_chunk("answer")
        return "partial answer"
    mock_llm = SimpleNamespace(chat_stream=fake_chat_stream)
    monkeypatch.setattr(orchestrator, "for_role", lambda role: mock_llm)
    context = RequestContext(conversation_id="stream-conversation")
    queue = asyncio.Queue()
    context.settings["stream_queue"] = queue
    result = asyncio.run(orchestrator.run_request("Bantu gue mikir", context))
    assert result["answer"] == "partial answer"
    assert queue.get_nowait() == "partial "
    assert queue.get_nowait() == "answer"


def test_context_truncation_is_logged_and_user_visible(isolated_database, monkeypatch):
    from app.core.settings_service import update_settings, get_all_settings
    original = get_all_settings()
    update_settings({"context": {"max_chars": 4000}})
    async def fake_chat(messages, **kwargs):
        return "Context-limited response."
    mock_llm = SimpleNamespace(chat=fake_chat)
    monkeypatch.setattr(orchestrator, "for_role", lambda role: mock_llm)
    context = RequestContext(conversation_id="context-test")
    result = asyncio.run(orchestrator.run_request("detail " * 10000, context))
    assert result["context_truncated"] is True
    assert result["status"] == "partial"
    assert any(event["stage"] == "context_budget" for event in result["events"])
    update_settings(original)


def test_research_with_metadata_only_fails_closed_without_model_synthesis(isolated_database, monkeypatch):
    from app.core.contracts import CapabilityResult, EvidenceItem
    async def fake_research(query, context, max_sources=5):
        return CapabilityResult('research', 'partial', 'Only metadata available.', evidence=[EvidenceItem(
            evidence_id='metadata-1', url='https://example.org/article', title='Search result title',
            retrieved_at='2026-10-20T00:00:00+00:00', open_status='failed', content_status='unavailable',
            snippet='Search snippet only', content='', source_domain='example.org', error='HTTP 403')])
    async def model_must_not_run(*args, **kwargs):
        raise AssertionError('Model synthesis must not run without readable research evidence.')
    monkeypatch.setattr(orchestrator, 'research', fake_research)
    mock_llm = SimpleNamespace(chat=model_must_not_run)
    monkeypatch.setattr(orchestrator, "for_role", lambda role: mock_llm)
    context = RequestContext(conversation_id='metadata-only')
    result = asyncio.run(orchestrator.run_request('Research this claim and provide sources', context))
    assert result['status'] == 'partial'
    assert result['verification']['status'] == 'not_run'
    assert 'not evidence' in result['answer'].lower() or 'bukan bukti' in result['answer'].lower()
    assert 'no_readable_source_content' in result['warnings']
    assert result['evidence'][0]['content_status'] == 'unavailable'


def test_research_with_zero_results_fails_without_model_synthesis(isolated_database, monkeypatch):
    from app.core.contracts import CapabilityResult
    async def fake_research(query, context, max_sources=5):
        return CapabilityResult('research', 'failed', 'No results.', warnings=['search_failed:ConnectError'])
    async def model_must_not_run(*args, **kwargs):
        raise AssertionError('Model synthesis must not run when retrieval failed.')
    monkeypatch.setattr(orchestrator, 'research', fake_research)
    mock_llm = SimpleNamespace(chat=model_must_not_run)
    monkeypatch.setattr(orchestrator, "for_role", lambda role: mock_llm)
    result = asyncio.run(orchestrator.run_request('Research the latest claim with sources', RequestContext(conversation_id='no-results')))
    assert result['status'] == 'failed'
    assert 'search_failed:ConnectError' in result['answer']
    assert result['verification']['status'] == 'not_run'


def test_research_never_reports_full_completion_without_semantic_verifier(isolated_database, monkeypatch):
    from app.core.contracts import CapabilityResult, EvidenceItem
    async def fake_research(query, context, max_sources=5):
        return CapabilityResult('research', 'completed', 'Two readable sources.', evidence=[
            EvidenceItem(evidence_id='11111111-1111-1111-1111-111111111111', url='https://source-one.example/report', title='Source One', retrieved_at='2026-10-20T00:00:00+00:00', open_status='opened', content_status='read', content='The official report states the project launched in 2024.', source_domain='source-one.example'),
            EvidenceItem(evidence_id='22222222-2222-2222-2222-222222222222', url='https://source-two.example/report', title='Source Two', retrieved_at='2026-10-20T00:00:00+00:00', open_status='opened', content_status='read', content='An independent report says the project launched during 2024.', source_domain='source-two.example')])
    async def fake_chat(messages, **kwargs):
        return 'The project launched in 2024. See https://source-one.example/report [11111111-1111-1111-1111-111111111111].'
    monkeypatch.setattr(orchestrator, 'research', fake_research)
    mock_llm = SimpleNamespace(chat=fake_chat)
    monkeypatch.setattr(orchestrator, 'for_role', lambda role: mock_llm)
    result = asyncio.run(orchestrator.run_request('Research the project and provide sources', RequestContext(conversation_id='semantic-gap')))
    assert result['status'] == 'partial'
    assert result['verification']['semantic_entailment_verified'] is False
    assert 'semantic_entailment_not_independently_verified' in result['verification']['warnings']
