import json
import logging
import re
import time
from typing import Dict, Optional

import requests

from config import (
    CATEGORIZATION_PROMPT,
    CLOUD_MODEL,
    DEFAULT_CATEGORIES,
    GEMINI_API_KEY,
    GEMINI_API_URL,
    LOCAL_API_URL,
    LOCAL_MODEL,
    MAX_RETRIES,
    PROVIDER,
    TIMEOUT,
)
from parser import DesktopEntry

logger = logging.getLogger(__name__)


class AppCategorizer:
    """Categorize Linux desktop apps using Local LLM (Ollama / OpenAI-compatible) or Cloud (Gemini)."""

    def __init__(
        self,
        provider: str = PROVIDER,
        model: Optional[str] = None,
        api_key: str = GEMINI_API_KEY,
        local_url: str = LOCAL_API_URL,
    ):
        self.provider = provider.lower()
        self.custom_model = model
        self.api_key = api_key
        self.local_url = local_url.rstrip("/")
        self.active_backend: Optional[str] = None
        self.active_model: Optional[str] = None
        self._resolve_backend()

    def _resolve_backend(self) -> None:
        if self.provider in ("auto", "local"):
            local_info = self._detect_local()
            if local_info:
                self.active_backend, self.active_model = local_info
                logger.info(
                    f"Using Local LLM ({self.active_backend}): {self.active_model} at {self.local_url}"
                )
                return
            if self.provider == "local":
                raise RuntimeError(
                    f"Local LLM not reachable at {self.local_url}. Start Ollama or llama-swap, or use --provider cloud."
                )
            logger.info("Local LLM unreachable, falling back to Cloud (Gemini API)...")

        if self.provider in ("auto", "cloud"):
            if not self.api_key:
                raise ValueError(
                    "No Local LLM reachable and GEMINI_API_KEY is not set for Cloud fallback."
                )
            self.active_backend = "cloud"
            self.active_model = self.custom_model or CLOUD_MODEL
            logger.info(f"Using Cloud LLM (Gemini REST): {self.active_model}")
            return

        raise ValueError(f"Unknown provider '{self.provider}'. Use auto, local, or cloud.")

    def _detect_local(self) -> Optional[tuple]:
        # 1. Try Ollama native API (/api/tags)
        try:
            resp = requests.get(f"{self.local_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                target = self.custom_model or LOCAL_MODEL
                if target in models:
                    return ("ollama", target)
                # Prefix match (e.g. gemma4) or first available non-embedding model
                for m in models:
                    if m.startswith(target.split(":")[0]):
                        return ("ollama", m)
                if models:
                    return ("ollama", models[0])
        except Exception:
            pass

        # 2. Try OpenAI-compatible API (/v1/models, e.g. llama-swap on :8080)
        for base_url in (self.local_url, "http://127.0.0.1:8080"):
            try:
                resp = requests.get(f"{base_url}/v1/models", timeout=3)
                if resp.status_code == 200:
                    self.local_url = base_url
                    data = resp.json().get("data", [])
                    models = [m.get("id", "") for m in data if m.get("id")]
                    target = self.custom_model or "coder-pro"
                    if target in models:
                        return ("openai", target)
                    if models:
                        return ("openai", models[0])
            except Exception:
                pass

        return None

    def _build_prompt(self, entries: Dict[str, DesktopEntry]) -> str:
        apps_text = [f"- {fname}: {entry.get_context()}" for fname, entry in entries.items()]
        return CATEGORIZATION_PROMPT.format(
            categories=", ".join(DEFAULT_CATEGORIES),
            applications="\n".join(apps_text),
        )

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": self.active_model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }
        resp = requests.post(f"{self.local_url}/api/generate", json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("response", "")

    def _call_openai(self, prompt: str) -> str:
        payload = {
            "model": self.active_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        resp = requests.post(
            f"{self.local_url}/v1/chat/completions", json=payload, timeout=TIMEOUT
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_cloud(self, prompt: str) -> str:
        model = self.active_model if self.active_backend == "cloud" else (self.custom_model or CLOUD_MODEL)
        url = GEMINI_API_URL.format(model=model)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }
        resp = requests.post(url, params={"key": self.api_key}, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _call_api(self, prompt: str) -> str:
        if self.active_backend == "ollama":
            try:
                return self._call_ollama(prompt)
            except Exception as e:
                if self.provider == "auto" and self.api_key:
                    logger.warning(f"Local Ollama call failed ({e}), falling back to Cloud...")
                    self.active_backend = "cloud"
                    return self._call_cloud(prompt)
                raise
        elif self.active_backend == "openai":
            try:
                return self._call_openai(prompt)
            except Exception as e:
                if self.provider == "auto" and self.api_key:
                    logger.warning(f"Local OpenAI call failed ({e}), falling back to Cloud...")
                    self.active_backend = "cloud"
                    return self._call_cloud(prompt)
                raise
        return self._call_cloud(prompt)

    def _parse_response(self, response_text: str) -> Optional[Dict[str, str]]:
        try:
            text = response_text.strip()
            # Strip <think>...</think> blocks if present from reasoning models
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            # Extract JSON object if surrounded by extra text
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                text = match.group(0)

            result = json.loads(text)
            if not isinstance(result, dict):
                return None

            for filename, category in list(result.items()):
                if category not in DEFAULT_CATEGORIES:
                    # Case-insensitive or singular match (e.g. "Game" -> "Games")
                    matched = next(
                        (
                            c
                            for c in DEFAULT_CATEGORIES
                            if c.lower() == str(category).lower().rstrip("s")
                            or c.lower().rstrip("s") == str(category).lower().rstrip("s")
                        ),
                        "Utility",
                    )
                    result[filename] = matched
            return result
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None

    def categorize(self, entries: Dict[str, DesktopEntry], batch_size: int = 30) -> Dict[str, str]:
        if not entries:
            return {}

        results: Dict[str, str] = {}
        remaining: Dict[str, DesktopEntry] = {}

        # Fast-path obvious games (Steam/Lutris/Heroic)
        for filename, entry in entries.items():
            if entry.is_obvious_game():
                results[filename] = "Games"
            else:
                remaining[filename] = entry

        if results:
            logger.info(f"Pre-categorized {len(results)} obvious game(s) into Games")

        filenames = list(remaining.keys())
        for i in range(0, len(filenames), batch_size):
            batch = {f: remaining[f] for f in filenames[i : i + batch_size]}
            logger.info(
                f"Processing batch {i // batch_size + 1} ({len(batch)} apps) via {self.active_backend}:{self.active_model}"
            )
            for attempt in range(MAX_RETRIES):
                try:
                    raw = self._call_api(self._build_prompt(batch))
                    parsed = self._parse_response(raw)
                    if parsed:
                        results.update(parsed)
                        break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{MAX_RETRIES} failed: {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2**attempt)

        return results
