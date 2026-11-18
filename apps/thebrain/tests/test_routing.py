from app.core.orchestrator import classify_request


def test_routing_research():
    assert classify_request("Cari sumber historis, URL, dan kutipan untuk presiden Amerika pada tanggal tertentu") == "research"


def test_routing_open_url():
    assert classify_request("Summarize this page https://example.org/report") == "open_url"


def test_routing_coding():
    assert classify_request("Debug this Python exception and implement a fix") == "coding"


def test_routing_chat_default():
    assert classify_request("Bantu gue mikir soal pilihan ini") == "chat"


def test_routing_app_builder_before_general_coding():
    assert classify_request("Build app for tracking recipes") == "app_builder"

def test_routing_stable_history_goes_to_chat():
    # "pertama" (first) is stable history, should NOT trigger research
    assert classify_request("Siapa presiden pertama Indonesia?") == "chat"

def test_routing_current_events_goes_to_research():
    # "sekarang" (now) triggers freshness routing
    assert classify_request("Siapa presiden Indonesia sekarang?") == "research"

def test_routing_latest_news_goes_to_research():
    assert classify_request("Berita terbaru tentang AI hari ini") == "research"
