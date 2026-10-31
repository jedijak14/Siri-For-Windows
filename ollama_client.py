"""Small, dependency-free client for a local Ollama server."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2:3b"

SYSTEM_PROMPT = """You are Siri for Windows, a local assistant.
Respond normally unless the user clearly asks to open Windows Photos or their
OneDrive folder. For those intents, respond with exactly one token:
[TOOL:PHOTOS_OPEN] or [TOOL:ONEDRIVE_OPEN].
Never emit other tool tokens. Do not claim an action has happened."""

POLISH_PROMPT = """Rewrite the user's text for clarity, grammar, and tone while
preserving its meaning. Return only the revised text, without quotes or
conversational commentary. Do not emit tool tokens."""


class OllamaError(RuntimeError):
    """Raised when Ollama cannot return a valid response."""


class OllamaClient:
    def __init__(self, base_url=DEFAULT_URL, model=None, timeout=300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._models = None
        self._capabilities = {}

    def available_models(self):
        request = Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise OllamaError(f"Ollama returned HTTP {exc.code}.") from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Timed out while listing local models after {self.timeout} seconds."
            ) from exc
        except URLError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.base_url}. "
                "Make sure Ollama is running locally."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("Ollama returned an invalid model list.") from exc

        models = body.get("models") if isinstance(body, dict) else None
        if not isinstance(models, list):
            raise OllamaError("Ollama returned an unexpected model list.")
        names = [
            item["name"]
            for item in models
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"].strip()
            and not item["name"].lower().endswith(":cloud")
        ]
        self._models = names
        return names

    def model_capabilities(self, model):
        if model in self._capabilities:
            return self._capabilities[model]
        request = Request(
            f"{self.base_url}/api/show",
            data=json.dumps({"model": model}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise OllamaError(f"Ollama could not inspect model {model} (HTTP {exc.code}).") from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Timed out while inspecting model {model} after {self.timeout} seconds."
            ) from exc
        except URLError as exc:
            raise OllamaError(f"Could not inspect local Ollama model {model}.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("Ollama returned invalid model capability data.") from exc
        capabilities = body.get("capabilities") if isinstance(body, dict) else None
        if not isinstance(capabilities, list):
            capabilities = []
        self._capabilities[model] = capabilities
        return capabilities

    def select_model(self, vision_required=False):
        if self.model and (not vision_required or "vision" in self.model_capabilities(self.model)):
            return self.model
        models = self._models if self._models is not None else self.available_models()
        if not models:
            raise OllamaError("No local Ollama models found. Install a model first.")
        candidates = [self.model] if self.model in models else []
        candidates.extend(model for model in models if model not in candidates)
        if vision_required:
            for candidate in candidates:
                if "vision" in self.model_capabilities(candidate):
                    self.model = candidate
                    return candidate
            raise OllamaError(
                "No installed local model advertises vision support. "
                "Install a local vision-capable Ollama model and try again."
            )
        self.model = DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]
        return self.model

    def generate(self, prompt, system_prompt=SYSTEM_PROMPT, image_data=None):
        payload = {
            "model": self.select_model(vision_required=bool(image_data)),
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
        }
        if image_data:
            payload["images"] = image_data
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise OllamaError(f"Ollama returned HTTP {exc.code}.") from exc
        except TimeoutError as exc:
            raise OllamaError(
                f"Local inference timed out after {self.timeout} seconds."
            ) from exc
        except URLError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.base_url}. "
                "Make sure Ollama is running locally."
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError("Ollama returned an invalid JSON response.") from exc

        if not isinstance(body, dict):
            raise OllamaError("Ollama returned an unexpected response shape.")
        answer = body.get("response")
        if not isinstance(answer, str):
            raise OllamaError("Ollama response did not contain text.")
        return answer.strip()

    def polish_text(self, text):
        return self.generate(text, system_prompt=POLISH_PROMPT)
