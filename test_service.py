import unittest
import json
from io import BytesIO
from unittest.mock import patch

from ollama_client import DEFAULT_MODEL, OllamaClient, OllamaError
from desktop_ui import _orb_color
from speech import listen_once, speak


class OllamaClientTests(unittest.TestCase):
    @patch("ollama_client.urlopen")
    def test_generate_posts_local_model_json(self, urlopen_mock):
        urlopen_mock.side_effect = [
            BytesIO(json.dumps({"models": [{"name": DEFAULT_MODEL}]}).encode()),
            BytesIO(json.dumps({"response": "Hello"}).encode()),
        ]

        answer = OllamaClient().generate("Hi")

        self.assertEqual(answer, "Hello")
        request = urlopen_mock.call_args_list[1].args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/generate")
        self.assertEqual(json.loads(request.data)["model"], DEFAULT_MODEL)
        self.assertFalse(json.loads(request.data)["stream"])

    def test_auto_select_prefers_requested_local_model(self):
        client = OllamaClient()
        with patch.object(client, "available_models", return_value=["other:latest", DEFAULT_MODEL]):
            self.assertEqual(client.select_model(), DEFAULT_MODEL)

    def test_auto_select_falls_back_to_first_installed_model(self):
        client = OllamaClient()
        with patch.object(client, "available_models", return_value=["custom:latest"]):
            self.assertEqual(client.select_model(), "custom:latest")

    def test_auto_select_reports_when_no_models_are_installed(self):
        client = OllamaClient()
        with patch.object(client, "available_models", return_value=[]):
            with self.assertRaisesRegex(OllamaError, "No local Ollama models"):
                client.select_model()

    @patch("ollama_client.urlopen", side_effect=TimeoutError)
    def test_inference_timeout_is_reported_as_slow_local_inference(self, _urlopen_mock):
        client = OllamaClient(model="local:latest", timeout=2)
        with self.assertRaisesRegex(OllamaError, "Local inference timed out after 2 seconds"):
            client.generate("hello")

    @patch("ollama_client.urlopen")
    def test_model_discovery_excludes_cloud_models(self, urlopen_mock):
        urlopen_mock.return_value = BytesIO(
            json.dumps(
                {"models": [{"name": "local:latest"}, {"name": "remote:cloud"}]}
            ).encode()
        )
        self.assertEqual(OllamaClient().available_models(), ["local:latest"])

    def test_vision_selection_uses_an_installed_vision_model(self):
        client = OllamaClient()
        client._models = ["gpt-oss:20b", "muse-glimmer:latest"]
        with patch.object(
            client,
            "model_capabilities",
            side_effect=[["completion"], ["completion", "vision"]],
        ):
            self.assertEqual(client.select_model(vision_required=True), "muse-glimmer:latest")

    def test_vision_selection_fails_explicitly_without_vision_model(self):
        client = OllamaClient()
        client._models = ["text-only:latest"]
        with patch.object(client, "model_capabilities", return_value=["completion"]):
            with self.assertRaisesRegex(OllamaError, "No installed local model"):
                client.select_model(vision_required=True)

    @patch("ollama_client.urlopen")
    def test_image_generation_includes_image_data(self, urlopen_mock):
        urlopen_mock.return_value = BytesIO(json.dumps({"response": "A cat"}).encode())
        client = OllamaClient(model="muse-glimmer:latest")
        with patch.object(client, "model_capabilities", return_value=["vision"]):
            self.assertEqual(client.generate("Describe it", image_data=["abc123"]), "A cat")
        request = urlopen_mock.call_args.args[0]
        self.assertEqual(json.loads(request.data)["images"], ["abc123"])

    @patch("ollama_client.urlopen")
    def test_text_polish_uses_no_filler_system_prompt(self, urlopen_mock):
        urlopen_mock.side_effect = [
            BytesIO(json.dumps({"models": [{"name": DEFAULT_MODEL}]}).encode()),
            BytesIO(json.dumps({"response": "Revised text."}).encode()),
        ]
        client = OllamaClient()
        self.assertEqual(client.polish_text("rough text"), "Revised text.")
        payload = json.loads(urlopen_mock.call_args_list[1].args[0].data)
        self.assertIn("Return only the revised text", payload["system"])
        self.assertEqual(payload["prompt"], "rough text")

    def test_orb_palette_uses_valid_hex_colors(self):
        self.assertRegex(_orb_color(0.0), r"^#[0-9a-f]{6}$")
        self.assertRegex(_orb_color(1.0), r"^#[0-9a-f]{6}$")


class SpeechTests(unittest.TestCase):
    @patch("speech.sys.platform", "win32")
    @patch("speech.subprocess.run")
    def test_speak_passes_text_via_stdin(self, run_mock):
        run_mock.return_value = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        speak("hello; harmless text")
        args = run_mock.call_args.args[0]
        self.assertEqual(args[0], "powershell.exe")
        self.assertEqual(run_mock.call_args.kwargs["input"], "hello; harmless text")
        self.assertNotIn("hello; harmless text", args)

    @patch("speech.sys.platform", "win32")
    @patch("speech.subprocess.run")
    def test_listen_uses_windows_dictation_engine(self, run_mock):
        run_mock.return_value = type(
            "Result", (), {"returncode": 0, "stdout": "recognized words", "stderr": ""}
        )()
        self.assertEqual(listen_once(), "recognized words")
        self.assertIn("DictationGrammar", run_mock.call_args.args[0][-1])


if __name__ == "__main__":
    unittest.main()
