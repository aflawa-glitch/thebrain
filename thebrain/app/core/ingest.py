from __future__ import annotations
import io
from pypdf import PdfReader
from fastapi import HTTPException

def extract(filename: str, media_type: str, raw: bytes) -> str:
    if media_type.startswith("text/") or filename.lower().endswith((".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".csv", ".xml", ".html", ".css", ".sql", ".sh", ".log")):
        return raw.decode("utf-8", errors="replace")
    elif media_type == "application/pdf" or filename.lower().endswith(".pdf"):
        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
            if not text.strip():
                raise HTTPException(415, "Scanned or empty PDF is unsupported (no extractable text).")
            return text
        except Exception as e:
            raise HTTPException(415, f"Failed to parse PDF: {str(e)}")
    else:
        raise HTTPException(415, f"Unsupported file type for text extraction: {media_type}")
