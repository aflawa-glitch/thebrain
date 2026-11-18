from __future__ import annotations

from typing import Any
import httpx

from .config import settings


class LLMError(RuntimeError):
    def __init__(self, category: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable


class OpenAICompatibleClient:
    """Client for llama.cpp's OpenAI-compatible endpoint or another compatible local server."""
    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = timeout or settings.llm_timeout_seconds

    async def chat(self, messages: list[dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 1200) -> str:
        if not settings.llm_enabled:
            raise LLMError("llm_disabled", "Local language model is disabled by configuration.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise LLMError("empty_model_response", "The model returned an empty response.", retryable=True)
                return content.strip()
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError("llm_timeout", f"Model request exceeded {self.timeout:g}s timeout.", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError("llm_http_error", f"Model server returned HTTP {exc.response.status_code}.", retryable=exc.response.status_code >= 500) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
            raise LLMError("llm_connection_or_protocol_error", f"Could not complete a valid request to the model server ({type(exc).__name__}).", retryable=True) from exc


    async def chat_stream(self, messages: list[dict[str, str]], on_chunk, *, temperature: float = 0.2, max_tokens: int = 1200) -> str:
        """Stream OpenAI-compatible chat completion chunks and return the assembled response."""
        if not settings.llm_enabled:
            raise LLMError("llm_disabled", "Local language model is disabled by configuration.")
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        assembled: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/chat/completions", json=payload,
                                         headers={"Authorization": f"Bearer {settings.llm_api_key}"}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = __import__("json").loads(data)
                            chunk = event.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        except (ValueError, KeyError, IndexError, TypeError):
                            continue
                        if chunk:
                            assembled.append(chunk)
                            await on_chunk(chunk)
            result = "".join(assembled).strip()
            if not result:
                raise LLMError("empty_stream_response", "The model stream returned no text.", retryable=True)
            return result
        except LLMError:
            raise
        except httpx.TimeoutException as exc:
            raise LLMError("llm_timeout", f"Model stream exceeded {self.timeout:g}s timeout.", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError("llm_stream_http_error", f"Model streaming endpoint returned HTTP {exc.response.status_code}.", retryable=exc.response.status_code >= 500) from exc
        except httpx.HTTPError as exc:
            raise LLMError("llm_stream_connection_error", f"Model stream connection failed ({type(exc).__name__}).", retryable=True) from exc

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 5)) as client:
                response = await client.get(f"{self.base_url}/models", headers={"Authorization": f"Bearer {settings.llm_api_key}"})
                response.raise_for_status()
                return {"status": "reachable", "endpoint": self.base_url, "models": response.json().get("data", [])}
        except Exception as exc:
            return {"status": "unavailable", "endpoint": self.base_url, "error_category": "llm_health_check_failed", "detail": type(exc).__name__}
