"""Google Gemini (free tier) for writing and reviewing scripts."""
from __future__ import annotations

import os
import re
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class Gemini:
    def __init__(self, models: list[str], log=print):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.log = log
        found = self._discover()
        # configured names first (if they exist), then the newest Flash models this key can use
        self.models = [m for m in models if not found or m in found] + [m for m in found if m not in models]
        if not self.models:
            self.models = models
        log(f"  Gemini models to try: {', '.join(self.models[:4])}")

    def _discover(self) -> list[str]:
        """List text models this key can call, newest Flash first (Google renames models often)."""
        try:
            names = []
            for m in self.client.models.list():
                name = (m.name or "").removeprefix("models/")
                actions = getattr(m, "supported_actions", None) or []
                if "flash" not in name or (actions and "generateContent" not in actions):
                    continue
                if any(x in name for x in ("image", "tts", "audio", "live", "embedding", "thinking-exp")):
                    continue
                names.append(name)
        except Exception as e:  # noqa: BLE001
            self.log(f"  could not list Gemini models: {e}")
            return []

        def key(n: str):
            nums = [int(x) if x.isdigit() else 0 for x in re.findall(r"\d+", n.split("flash")[0])]
            return ("lite" in n, "preview" in n or "exp" in n, [-x for x in nums], n)
        return sorted(set(names), key=key)

    def json(self, system: str, prompt: str, schema: type[T], temperature: float = 0.9) -> T:
        """Structured JSON output, trying each model in order and backing off on rate limits."""
        last: Exception | None = None
        for model in self.models:
            for attempt in range(4):
                try:
                    resp = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system,
                            temperature=temperature,
                            response_mime_type="application/json",
                            response_schema=schema,
                        ),
                    )
                    if resp.parsed is not None:
                        return resp.parsed
                    return schema.model_validate_json(resp.text or "")
                except errors.ClientError as e:
                    last = e
                    if e.code == 429:  # free-tier rate limit: wait and retry
                        wait = 20 * (attempt + 1)
                        self.log(f"    {model}: rate limited, waiting {wait}s")
                        time.sleep(wait)
                        continue
                    self.log(f"    {model}: {e.code} {e.message}")
                    break  # model unavailable / bad request -> next model
                except errors.ServerError as e:
                    last = e
                    self.log(f"    {model}: server error {e.code}, retrying")
                    time.sleep(10 * (attempt + 1))
                except Exception as e:  # noqa: BLE001  (e.g. JSON that fails validation)
                    last = e
                    self.log(f"    {model}: bad output ({e}); retrying")
        raise RuntimeError(f"All Gemini models failed: {last}")
