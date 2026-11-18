from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse
from .contracts import EvidenceItem


def validate_evidence(evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
    results = []
    for item in evidence:
        parsed = urlparse(item.url)
        valid_url = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        results.append({
            "evidence_id": item.evidence_id,
            "url_valid": valid_url,
            "content_read": item.open_status == "opened" and item.content_status == "read",
            "quote_eligible": item.open_status == "opened" and item.content_status == "read" and bool(item.content.strip()),
            "domain": item.source_domain or parsed.netloc,
            "warnings": (["invalid_or_non_http_url"] if not valid_url else []) + (["page_content_not_read"] if not (item.open_status == "opened" and item.content_status == "read") else []),
        })
    return results


def validate_verbatim_quote(quote: str, evidence: EvidenceItem) -> bool:
    """Exact normalized substring check; no model-based paraphrase acceptance."""
    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()
    return bool(quote.strip()) and normalize(quote) in normalize(evidence.content)


def classify_claim_support(claim: str, evidence: list[EvidenceItem]) -> dict[str, Any]:
    tokens = {t.lower() for t in re.findall(r"[\w'-]{4,}", claim)}
    scored = []
    for item in evidence:
        if item.open_status != "opened" or item.content_status != "read":
            continue
        content_tokens = {t.lower() for t in re.findall(r"[\w'-]{4,}", item.content)}
        overlap = len(tokens & content_tokens) / max(1, len(tokens))
        scored.append({"evidence_id": item.evidence_id, "url": item.url, "token_overlap": round(overlap, 3)})
    scored.sort(key=lambda row: row["token_overlap"], reverse=True)
    return {"claim": claim, "support_status": "needs_human_or_model_review" if scored else "unsupported_no_read_content", "candidate_evidence": scored[:3]}


def verify_research_answer(answer: str, request_text: str, evidence: list[EvidenceItem]) -> dict[str, Any]:
    """Deterministic checks for source provenance and requested quote/access-date output.

    This does not prove semantic entailment. It catches common provenance/quote regressions and
    leaves semantic claim support explicitly unresolved for a separate verifier.
    """
    import hashlib
    from urllib.parse import urlparse, urlunparse

    def normalize_url(value: str) -> str:
        value = value.rstrip(".,;:!?)\\]")
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return value
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))

    read_items = [item for item in evidence if item.open_status == "opened" and item.content_status == "read" and item.content.strip()]
    verified_urls = {normalize_url(item.url) for item in read_items}
    user_urls = {normalize_url(url) for url in re.findall(r"https?://[^\s<>\]\[()]+", request_text)}
    answer_urls = {normalize_url(url) for url in re.findall(r"https?://[^\s<>\]\[()]+", answer)}
    warnings: list[str] = []
    unsupported_urls = sorted(url for url in answer_urls if url not in verified_urls and url not in user_urls)
    if unsupported_urls:
        warnings.append("answer_contains_url_without_input_or_retrieval_provenance")
    asks_sources = bool(re.search(r"\b(urls?|sources?|citations?|access dates?|tanggal akses|sumber)\b", request_text, re.I))
    asks_quotes = bool(re.search(r"\b(verbatim|quote|quotation|supporting quote|kutipan|kutipan pendukung)\b", request_text, re.I))
    if asks_sources and not answer_urls:
        warnings.append("required_source_url_missing")
    if asks_quotes:
        if not re.search(r"[\"“][^\"”]{12,}[\"”]", answer):
            warnings.append("requested_supporting_quote_missing_or_not_verbatim")
    quote_candidates = re.findall(r"[\"“]([^\"”]{13,})[\"”]", answer)
    invalid_quotes = []
    for quote in quote_candidates:
        if not any(re.sub(r"\s+", " ", quote).strip() in re.sub(r"\s+", " ", item.content).strip() for item in read_items):
            invalid_quotes.append(quote)
    if invalid_quotes:
        warnings.append("requested_supporting_quote_missing_or_not_verbatim")
    if asks_sources and re.search(r"\b(access dates?|date accessed|tanggal akses|diakses pada)\b", request_text, re.I):
        if not re.search(r"\b(accessed|access date|tanggal akses|diakses pada)\b", answer, re.I):
            warnings.append("required_access_date_missing")
    ids = {item.evidence_id for item in read_items}
    cited_ids = set(re.findall(r"\[([0-9a-fA-F-]{8,})\]", answer))
    if read_items and not (ids & cited_ids):
        warnings.append("claim_evidence_mapping_missing")
    candidate_claims = []
    unsupported_claims = []
    if read_items:
        raw_claims = re.split(r"(?<=[.!?])\s+|\n(?=\s*(?:[-*] |\d+\. ))", answer)
        for raw in raw_claims:
            claim = re.sub(r"^\s*(?:[-*] |\d+\. |#{1,6} )", "", raw).strip()
            if len(claim) < 28 or claim.startswith("**Peringatan QC") or claim.startswith("**Status verifikasi"):
                continue
            support = classify_claim_support(claim, read_items)
            best = support["candidate_evidence"][0] if support["candidate_evidence"] else None
            entry = {"claim_excerpt": claim[:280], "candidate_evidence": best, "status": "candidate_only_not_semantically_verified" if best and best["token_overlap"] >= 0.2 else "no_lexical_support_candidate"}
            candidate_claims.append(entry)
            if entry["status"] == "no_lexical_support_candidate":
                unsupported_claims.append(claim[:280])
        if unsupported_claims:
            warnings.append("claims_without_lexical_evidence_candidate")
    domains = {item.source_domain.lower().removeprefix("www.") for item in read_items if item.source_domain}
    hashes: dict[str, list[str]] = {}
    for item in read_items:
        digest = hashlib.sha256(re.sub(r"\s+", " ", item.content).strip().lower().encode()).hexdigest()
        hashes.setdefault(digest, []).append(item.url)
    duplicates = [urls for urls in hashes.values() if len(urls) > 1]
    if len(domains) < 2 and len(read_items) > 0:
        warnings.append("independent_source_corroboration_not_established")
    if duplicates:
        warnings.append("duplicate_or_syndicated_content_detected")
    explicit_year = bool(re.search(r"\b(?:19|20)\d{2}\b", request_text))
    temporal_request = bool(re.search(r"historical|history|on January|on February|as of|tanggal|pada tanggal|historis|sejarah|per [0-9]", request_text, re.I))
    if explicit_year and temporal_request and read_items and not any(item.published_at for item in read_items):
        warnings.append("temporal_relevance_not_established_by_publisher_date_metadata")
    return {
        "status": "partial" if warnings else "passed_deterministic_checks",
        "warnings": list(dict.fromkeys(warnings)),
        "read_source_count": len(read_items),
        "unique_domains": sorted(domains),
        "answer_urls": sorted(answer_urls),
        "unsupported_urls": unsupported_urls,
        "quote_candidates_checked": len(quote_candidates),
        "invalid_quote_count": len(invalid_quotes),
        "cited_evidence_ids": sorted(ids & cited_ids),
        "candidate_claim_evidence_mapping": candidate_claims,
        "claims_without_lexical_evidence_candidate": unsupported_claims,
        "semantic_entailment_verified": False,
        "note": "These checks validate URL provenance and exact quote presence only; they do not prove every factual claim is entailed by its source.",
    }
