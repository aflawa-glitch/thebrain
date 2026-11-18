from __future__ import annotations
import uuid
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import re
from typing import Any
from app.core.contracts import CapabilityResult, EvidenceItem, RequestContext, utc_now

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

async def _search_duckduckgo(query: str) -> list[dict[str, str]]:
    # Use the GET method, which is less likely to be blocked by DDG
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}
    
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
        try:
            print(f"🔍 Searching DDG for: {query}")
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        except Exception as e:
            print(f"❌ DDG Search failed: {e}")
            return []
            
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.find_all("a", class_="result__a")[:5]:
        href = a.get("href")
        if href and "uddg=" in href:
            actual_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
        else:
            actual_url = href
            
        if actual_url and actual_url.startswith("http"):
            results.append({
                "title": a.get_text(strip=True),
                "url": actual_url
            })
            
    print(f"✅ DDG found {len(results)} results.")
    return results

async def _fetch_page(url: str) -> tuple[str, str]:
    """Returns (status, text_content_or_error)."""
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return "failed", f"HTTP {resp.status_code}"
            
            soup = BeautifulSoup(resp.text, "html.parser")
            for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
                s.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            if len(text.strip()) < 50:
                return "failed", "Page content too short (possible bot block)"
                
            return "read", text
        except Exception as e:
            return "failed", str(e)

async def research(query: str, context: RequestContext, max_sources: int = 5) -> CapabilityResult:
    results = await _search_duckduckgo(query)
    
    if not results:
        return CapabilityResult("research", "failed", "No search results found.", warnings=["search_failed"])
        
    evidence_items = []
    for i, res in enumerate(results[:max_sources]):
        if context.cancel_event and context.cancel_event.is_set():
            break
            
        status, content = await _fetch_page(res["url"])
        error_msg = content if status == "failed" else None
        
        evidence_items.append(EvidenceItem(
            evidence_id=str(uuid.uuid4()),
            url=res["url"],
            title=res["title"],
            retrieved_at=utc_now(),
            open_status="opened" if status == "read" else "failed",
            content_status="read" if status == "read" else "unavailable",
            content=content if status == "read" else "",
            snippet="",
            source_domain=res["url"].split("/")[2] if "://" in res["url"] else "",
            error=error_msg
        ))
        
    readable_count = sum(1 for e in evidence_items if e.content_status == "read")
    if readable_count == 0:
        return CapabilityResult("research", "failed", "All sources failed to open.", evidence=evidence_items, warnings=["page_content_not_read"])
        
    return CapabilityResult("research", "completed", f"Successfully read {readable_count} sources.", evidence=evidence_items)

async def open_user_url(url: str, context: RequestContext) -> CapabilityResult:
    status, content = await _fetch_page(url)
    error_msg = content if status == "failed" else None
    
    evidence = EvidenceItem(
        evidence_id=str(uuid.uuid4()),
        url=url,
        title="User provided URL",
        retrieved_at=utc_now(),
        open_status="opened" if status == "read" else "failed",
        content_status="read" if status == "read" else "unavailable",
        content=content if status == "read" else "",
        snippet="",
        source_domain=url.split("/")[2] if "://" in url else "",
        error=error_msg
    )
    return CapabilityResult("open_url", "completed" if status == "read" else "failed", "URL fetched", evidence=[evidence])
