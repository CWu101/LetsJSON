from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from typing import Literal

from openai import OpenAI


class LetsJSONError(Exception):
    pass


class LetsJSONValidationError(LetsJSONError):
    pass


class LetsJSONGenerationError(LetsJSONError):
    pass


class LetsJSON:
    def __init__(
        self, *, base_url: str, model: str, api_key: str, temperature: float = 0.2, repeat: int = 3
    ) -> None:
        if not model:
            raise ValueError("model is required")
        if not api_key:
            raise ValueError("api_key is required")
        if not base_url:
            raise ValueError("base_url is required")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.repeat = repeat
        self.temperature = temperature
        self.model = model

    def gen(
        self, prompt: str, schema: dict[str, Any], on_failure: Literal["raise", "none"] = "raise"
    ) -> dict[str, Any] | None:
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dict")
        if on_failure not in {"raise", "none"}:
            raise ValueError("on_failure must be 'raise' or 'none'")

        last_error: Exception | None = None
        for attempt in range(1, self.repeat + 1):
            # print(f"Attempt {attempt} to generate JSON...")
            full_prompt = self._build_prompt(prompt, schema, attempt, last_error)
            try:
                raw = self._call_model(full_prompt)
                data = self._parse_json(raw)
                self._validate(data, schema)
                return data
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if on_failure == "none":
            return None

        raise LetsJSONGenerationError(
            f"Failed to generate valid JSON after {self.repeat} attempts. "
            f"Last error: {last_error}"
        )

    def gen_stream(
        self,
        prompt: str,
        schema: dict[str, Any],
        on_failure: Literal["raise", "none"] = "raise",
        on_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any] | None:
        if not isinstance(schema, dict):
            raise TypeError("schema must be a dict")
        if on_failure not in {"raise", "none"}:
            raise ValueError("on_failure must be 'raise' or 'none'")

        last_error: Exception | None = None
        for attempt in range(1, self.repeat + 1):
            full_prompt = self._build_prompt(prompt, schema, attempt, last_error)
            try:
                raw = self._call_model_stream(full_prompt, on_chunk=on_chunk)
                data = self._parse_json(raw)
                self._validate(data, schema)
                return data
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if on_failure == "none":
            return None

        raise LetsJSONGenerationError(
            f"Failed to generate valid JSON after {self.repeat} attempts. "
            f"Last error: {last_error}"
        )

    def _build_prompt(
        self, prompt: str, schema: dict[str, Any], attempt: int, last_error: Exception | None
    ) -> str:
        schema_text = self._schema_to_text(schema)
        fix_hint = ""
        if last_error is not None:
            fix_hint = f"\nPrevious output was invalid: {last_error}\nPlease fix it."

        return (
            "Return ONLY a valid JSON object with no markdown, no explanation.\n"
            f"User request: {prompt}\n"
            f"Required JSON schema: {schema_text}\n"
            f"Attempt: {attempt}\n"
            f"{fix_hint}\n"
            f"Use the language that the user said.\n"
        )

    def _call_model(self, prompt: str) -> str:
        chat_error: Exception | None = None
        chat = getattr(self.client, "chat", None)
        completions = getattr(chat, "completions", None) if chat is not None else None
        if completions is not None and hasattr(completions, "create"):
            try:
                result = completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                )
                choices = getattr(result, "choices", None) or []
                if choices:
                    message = getattr(choices[0], "message", None)
                    content = getattr(message, "content", "")
                    if isinstance(content, str):
                        return content
            except Exception as exc:  # noqa: BLE001
                chat_error = exc

        responses = getattr(self.client, "responses", None)
        if responses is not None and hasattr(responses, "create"):
            try:
                result = responses.create(
                    model=self.model, temperature=self.temperature, input=prompt
                )
                text = getattr(result, "output_text", None)
                if isinstance(text, str) and text.strip():
                    return text

                # Fallback: collect text chunks from response output structure.
                output = getattr(result, "output", None) or []
                chunks: list[str] = []
                for item in output:
                    content = getattr(item, "content", None) or []
                    for part in content:
                        part_text = getattr(part, "text", None)
                        if isinstance(part_text, str):
                            chunks.append(part_text)
                if chunks:
                    return "\n".join(chunks)
            except Exception:  # noqa: BLE001
                pass

        if chat_error is not None:
            raise LetsJSONGenerationError(
                "chat.completions.create failed and no compatible responses.create fallback "
                f"succeeded. Original error: {chat_error}"
            )

        raise LetsJSONGenerationError(
            "Unsupported client: expected OpenAI client with chat.completions.create or "
            "responses.create."
        )

    def _call_model_stream(self, prompt: str, on_chunk: Callable[[str], None] | None = None) -> str:
        chat_error: Exception | None = None
        chat = getattr(self.client, "chat", None)
        completions = getattr(chat, "completions", None) if chat is not None else None
        if completions is not None and hasattr(completions, "create"):
            try:
                stream = completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                chunks: list[str] = []
                for event in stream:
                    choices = getattr(event, "choices", None) or []
                    if not choices:
                        continue
                    delta = getattr(choices[0], "delta", None)
                    content = getattr(delta, "content", None)
                    if isinstance(content, str):
                        chunks.append(content)
                        if on_chunk is not None:
                            on_chunk(content)
                        continue
                    if isinstance(content, list):
                        for part in content:
                            part_text = getattr(part, "text", None)
                            if isinstance(part_text, str):
                                chunks.append(part_text)
                                if on_chunk is not None:
                                    on_chunk(part_text)
                if chunks:
                    return "".join(chunks)
            except Exception as exc:  # noqa: BLE001
                chat_error = exc

        responses = getattr(self.client, "responses", None)
        if responses is not None and hasattr(responses, "create"):
            try:
                stream = responses.create(
                    model=self.model,
                    temperature=self.temperature,
                    input=prompt,
                    stream=True,
                )
                chunks: list[str] = []
                for event in stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "response.output_text.delta":
                        delta = getattr(event, "delta", None)
                        if isinstance(delta, str):
                            chunks.append(delta)
                            if on_chunk is not None:
                                on_chunk(delta)
                if chunks:
                    return "".join(chunks)
            except Exception:  # noqa: BLE001
                pass

        if chat_error is not None:
            raise LetsJSONGenerationError(
                "chat.completions.create(stream=True) failed and no compatible "
                "responses.create(stream=True) fallback succeeded. "
                f"Original error: {chat_error}"
            )

        raise LetsJSONGenerationError(
            "Unsupported client: expected OpenAI client with chat.completions.create or "
            "responses.create."
        )

    def _parse_json(self, text: str) -> Any:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        for candidate in self._extract_json_candidates(text):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        raise LetsJSONValidationError("Model output is not valid JSON.")

    def _extract_json_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []

        fenced = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
        candidates.extend(fenced)

        stack: list[str] = []
        start = -1
        for idx, ch in enumerate(text):
            if ch in "{[":
                if not stack:
                    start = idx
                stack.append(ch)
            elif ch in "}]":
                if not stack:
                    continue
                opener = stack.pop()
                if (opener, ch) not in {("{", "}"), ("[", "]")}:
                    stack.clear()
                    start = -1
                    continue
                if not stack and start >= 0:
                    candidates.append(text[start : idx + 1])
                    start = -1
        return candidates

    def _schema_to_text(self, spec: Any) -> str:
        if isinstance(spec, dict):
            inner = ", ".join(f'"{k}": {self._schema_to_text(v)}' for k, v in spec.items())
            return f"{{{inner}}}"
        if isinstance(spec, list):
            if len(spec) != 1:
                raise TypeError("List schema must contain exactly one element schema.")
            return f"[{self._schema_to_text(spec[0])}]"
        if isinstance(spec, type):
            return spec.__name__
        raise TypeError(f"Unsupported schema spec: {spec!r}")

    def _validate(self, data: Any, schema: Any, path: str = "root") -> None:
        if isinstance(schema, dict):
            if not isinstance(data, dict):
                raise LetsJSONValidationError(f"{path} must be an object")
            expected_keys = set(schema.keys())
            actual_keys = set(data.keys())
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            if missing:
                raise LetsJSONValidationError(f"{path} missing keys: {sorted(missing)}")
            if extra:
                raise LetsJSONValidationError(f"{path} has unexpected keys: {sorted(extra)}")
            for key, sub_schema in schema.items():
                self._validate(data[key], sub_schema, f"{path}.{key}")
            return

        if isinstance(schema, list):
            if len(schema) != 1:
                raise TypeError("List schema must contain exactly one element schema.")
            if not isinstance(data, list):
                raise LetsJSONValidationError(f"{path} must be a list")
            for idx, item in enumerate(data):
                self._validate(item, schema[0], f"{path}[{idx}]")
            return

        if isinstance(schema, type):
            if schema is int:
                if not (isinstance(data, int) and not isinstance(data, bool)):
                    raise LetsJSONValidationError(f"{path} must be int")
                return
            if schema is float:
                if not (
                    (isinstance(data, float) and not isinstance(data, bool))
                    or (isinstance(data, int) and not isinstance(data, bool))
                ):
                    raise LetsJSONValidationError(f"{path} must be float")
                return
            if schema is bool:
                if not isinstance(data, bool):
                    raise LetsJSONValidationError(f"{path} must be bool")
                return
            if schema is str:
                if not isinstance(data, str):
                    raise LetsJSONValidationError(f"{path} must be str")
                return
            if schema is list:
                if not isinstance(data, list):
                    raise LetsJSONValidationError(f"{path} must be list")
                return
            if schema is dict:
                if not isinstance(data, dict):
                    raise LetsJSONValidationError(f"{path} must be object")
                return
            if not isinstance(data, schema):
                raise LetsJSONValidationError(f"{path} must be {schema.__name__}")
            return

        raise TypeError(f"Unsupported schema spec at {path}: {schema!r}")
