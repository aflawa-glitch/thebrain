from app.core.audit_store import list_events, list_evidence

def test_list_events_returns_empty_for_unknown_trace():
    events = list_events("unknown-trace-123")
    assert events == []

def test_list_evidence_returns_empty_for_unknown_trace():
    evidence = list_evidence("unknown-trace-123")
    assert evidence == []
