import pytest
from app.core.contracts import utc_now
import app.main as main
from app.core import task_registry


def test_health_settings_capabilities_and_glossary(client):
    assert client.get('/api/health').status_code == 200
    caps = client.get('/api/capabilities').json()
    assert caps['count'] >= 4
    assert client.get('/api/settings').json()['settings']['global']['language'] == 'id-ID-slang'
    created = client.post('/api/glossary', json={'term':'API_TEST_TERM','definition':'A test glossary definition','language':'test'})
    assert created.status_code == 200
    assert any(t['term'] == 'API_TEST_TERM' for t in client.get('/api/glossary').json()['terms'])
    assert client.delete('/api/glossary/API_TEST_TERM').status_code == 200


def test_chat_uses_orchestration_result_and_stores_trace(client, monkeypatch):
    async def fake_run_request(text, context, **kwargs):
        return {'trace_id':context.trace_id,'request_id':context.request_id,'conversation_id':context.conversation_id,'status':'completed','route':'chat','answer':'Test response from fake orchestrator.','events':[],'evidence':[],'warnings':[],'context_truncated':False}
    monkeypatch.setattr(main, 'run_request', fake_run_request)
    response = client.post('/api/chat', json={'message':'Hello Julian'})
    assert response.status_code == 200
    data = response.json()
    assert data['answer'] == 'Test response from fake orchestrator.'
    assert data['trace_id']
    history = client.get('/api/conversations/'+data['conversation_id']).json()['messages']
    assert [m['role'] for m in history] == ['user','assistant']


def test_stream_returns_result_event(client, monkeypatch):
    async def fake_run_request(text, context, **kwargs):
        return {'trace_id':context.trace_id,'request_id':context.request_id,'conversation_id':context.conversation_id,'status':'completed','route':'chat','answer':'Streamed test response.','events':[],'evidence':[],'warnings':[],'context_truncated':False}
    monkeypatch.setattr(main, 'run_request', fake_run_request)
    response = client.post('/api/chat/stream', json={'message':'Hello stream'})
    assert response.status_code == 200
    assert 'event: result' in response.text
    assert 'Streamed test response.' in response.text


def test_invalid_settings_are_rejected(client):
    response = client.put('/api/settings', json={'settings': {'context': {'max_chars': -1}}})
    assert response.status_code == 422


def test_nonpersistent_upload_is_available_for_current_task_then_discarded(client, monkeypatch):
    from app.core.settings_service import get_all_settings
    settings = get_all_settings()
    settings['privacy']['save_uploaded_content'] = False
    client.put('/api/settings', json={'settings': settings})
    conversation_id = client.post('/api/conversations').json()['conversation_id']
    upload = client.post(f'/api/uploads?conversation_id={conversation_id}', files={'file': ('notes.md', b'private temporary context phrase', 'text/markdown')})
    assert upload.status_code == 200 and upload.json()['persisted'] is False
    assert main._ephemeral_uploads[conversation_id][0]['extracted_text'] == 'private temporary context phrase'
    async def fake_run_request(text, context, **kwargs):
        assert 'private temporary context phrase' in kwargs['file_context']
        return {'trace_id':context.trace_id,'request_id':context.request_id,'conversation_id':context.conversation_id,'status':'completed','route':'file_analysis','answer':'Analyzed temporary file.','events':[],'evidence':[],'warnings':[],'context_truncated':False}
    monkeypatch.setattr(main, 'run_request', fake_run_request)
    response = client.post('/api/chat', json={'message':'Analyze the uploaded notes.md','conversation_id':conversation_id})
    assert response.status_code == 200
    assert conversation_id not in main._ephemeral_uploads
    with main.connect() as con:
        count = con.execute('SELECT COUNT(*) FROM uploads WHERE conversation_id=?', (conversation_id,)).fetchone()[0]
    assert count == 0


def test_schema_preflight_blocker_returns_actionable_diagnostic(client):
    main.app.state.startup_blocker = 'schema_incompatible: legacy settings table missing value_json'
    try:
        health = client.get('/api/health').json()
        blocked = client.get('/api/settings')
        assert health['status'] == 'blocked'
        assert health['database']['error_category'] == 'schema_incompatible'
        assert blocked.status_code == 503
        assert blocked.json()['stage'] == 'runtime_preflight'
        assert blocked.json()['next_step']
    finally:
        main.app.state.startup_blocker = None


def test_nonpersistent_upload_is_routed_as_file_analysis(client, monkeypatch):
    from app.core.settings_service import get_all_settings
    settings = get_all_settings()
    settings['privacy']['save_uploaded_content'] = False
    client.put('/api/settings', json={'settings': settings})
    conversation_id = client.post('/api/conversations').json()['conversation_id']
    upload = client.post(f'/api/uploads?conversation_id={conversation_id}', files={'file': ('notes.md', b'ephemeral routing proof', 'text/markdown')})
    assert upload.status_code == 200
    observed = {}
    async def fake_run_request(text, context, **kwargs):
        observed.update(kwargs)
        return {'trace_id':context.trace_id,'request_id':context.request_id,'conversation_id':context.conversation_id,'status':'completed','route':'file_analysis','answer':'Analyzed temporary file.','events':[],'evidence':[],'warnings':[],'context_truncated':False}
    monkeypatch.setattr(main, 'run_request', fake_run_request)
    response = client.post('/api/chat', json={'message':'Analyze this file','conversation_id':conversation_id})
    assert response.status_code == 200
    assert observed['has_files'] is True
    assert 'ephemeral routing proof' in observed['file_context']


def _minimal_text_pdf(text: str) -> bytes:
    from io import BytesIO
    # Small valid PDF fixture with a single Helvetica text run; no extra test dependency.
    escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        f'<< /Length {len(("BT /F1 12 Tf 72 720 Td (" + escaped + ") Tj ET").encode())} >>\nstream\nBT /F1 12 Tf 72 720 Td ({escaped}) Tj ET\nendstream'.encode(),
    ]
    out = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f'{index} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = len(out)
    out.extend(f'xref\n0 {len(offsets)}\n'.encode())
    out.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        out.extend(f'{offset:010d} 00000 n \n'.encode())
    out.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(out)


def test_pdf_upload_extracts_text_and_records_page_provenance(client):
    pdf_bytes = _minimal_text_pdf('Julian PDF extraction acceptance phrase')
    conversation_id = client.post('/api/conversations').json()['conversation_id']
    response = client.post(f'/api/uploads?conversation_id={conversation_id}', files={'file': ('acceptance.pdf', pdf_bytes, 'application/pdf')})
    assert response.status_code == 200, response.text
    assert response.json()['media_type'] == 'application/pdf'
    with main.connect() as con:
        row = con.execute('SELECT extracted_text FROM uploads WHERE conversation_id=? AND filename=?', (conversation_id, 'acceptance.pdf')).fetchone()
    assert row is not None
    assert '[PDF page 1]' in row['extracted_text']
    assert 'Julian PDF extraction acceptance phrase' in row['extracted_text']


def test_scanned_or_empty_pdf_fails_explicitly(client):
    from io import BytesIO
    from pypdf import PdfWriter
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buffer)
    conversation_id = client.post('/api/conversations').json()['conversation_id']
    response = client.post(f'/api/uploads?conversation_id={conversation_id}', files={'file': ('blank.pdf', buffer.getvalue(), 'application/pdf')})
    assert response.status_code == 415
    assert 'no extractable text' in response.json()['detail'].lower()


def test_ephemeral_upload_is_discarded_even_when_task_is_cancelled(client, monkeypatch):
    import asyncio
    from app.core.contracts import RequestContext
    conversation_id = client.post('/api/conversations').json()['conversation_id']
    main._ephemeral_uploads[conversation_id] = [{'filename': 'private.txt', 'extracted_text': 'private data', 'sha256': 'abc'}]
    async def cancel_request(*args, **kwargs):
        raise asyncio.CancelledError()
    monkeypatch.setattr(main, 'run_request', cancel_request)
    context = RequestContext(conversation_id=conversation_id)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main._execute_chat(main.ChatRequest(message='Analyze private file', conversation_id=conversation_id), context))
    assert conversation_id not in main._ephemeral_uploads


def test_cancel_endpoint_signals_event_and_cancels_active_task():
    import asyncio
    class FakeEvent:
        def __init__(self): self.was_set = False
        def set(self): self.was_set = True
    class FakeTask:
        def __init__(self): self.was_cancelled = False
        def done(self): return False
        def cancel(self): self.was_cancelled = True
    trace_id = 'cancel-test-trace'
    event, task = FakeEvent(), FakeTask()
    task_registry.register(trace_id, task, event)
    
    try:
        result = asyncio.run(main.cancel_task(trace_id))
        assert result['status'] == 'cancellation_requested'
        assert event.was_set is True
        assert task.was_cancelled is True
    finally:
        task_registry.pop(trace_id)


def test_health_does_not_claim_full_readiness_when_model_is_unavailable(client, monkeypatch):
    class UnavailableModel:
        async def health(self):
            return {"status": "unavailable", "error_category": "llm_health_check_failed"}
    monkeypatch.setattr(main, "for_role", lambda role: UnavailableModel())
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'degraded'
    assert payload['readiness']['phase1_ready'] is False
    assert payload['readiness']['model'] == 'unavailable'
