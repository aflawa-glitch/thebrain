import pytest
from fastapi import HTTPException
from app.core.ingest import extract

def test_extract_text_file():
    raw = b"Hello Julian"
    result = extract("test.txt", "text/plain", raw)
    assert result == "Hello Julian"

def test_extract_unsupported_file():
    with pytest.raises(HTTPException) as excinfo:
        extract("test.exe", "application/octet-stream", b"binary")
    assert excinfo.value.status_code == 415
