"""Non-invasive checks for the local assistant's runtime prerequisites."""

import sys

from ollama_client import DEFAULT_MODEL, DEFAULT_URL, OllamaClient, OllamaError


def main():
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.")
        return 1
    client = OllamaClient(timeout=3)
    try:
        model = client.select_model()
    except OllamaError as exc:
        print(exc)
        return 1

    print(f"Python {sys.version_info.major}.{sys.version_info.minor}: OK")
    print(f"Ollama endpoint {DEFAULT_URL}: OK")
    if model == DEFAULT_MODEL:
        print(f"Preferred model {model}: found")
    else:
        print(f"Auto-selected installed model: {model}")
    print("No startup, registry, or system-wide settings were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
