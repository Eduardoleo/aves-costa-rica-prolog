import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/Main"))
import azure_config as ac

class AzureTests(unittest.TestCase):
    def test_five_demo_cases_without_client(self):
        with patch.dict(os.environ, {"AVES_MODO_DEMO": "1"}):
            client = ac.ClienteAves()
            for color in ["verde", "rojo", "amarillo", "azul", "negro"]:
                result = client.create(messages=[{"content": color}])
                data = json.loads(result.choices[0].message.content)
                self.assertEqual(data["color"], color)
                self.assertTrue(data["simulado"])
                self.assertIsNone(client._client)

    def test_429_retries_once_and_explains(self):
        class Fake429(Exception): pass
        create = Mock(side_effect=Fake429())
        client = ac.ClienteAves()
        client._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        settings = {"AVES_MODO_DEMO": "0", "AZURE_OPENAI_ENDPOINT": "https://example.invalid", "AZURE_OPENAI_API_KEY": "[FICTICIO]", "AZURE_OPENAI_DEPLOYMENT": "[FICTICIO]", "AZURE_OPENAI_API_VERSION": "v1"}
        with patch.dict(os.environ, settings), patch.object(ac, "RateLimitError", Fake429), patch.object(ac.time, "sleep") as sleep:
            with self.assertRaisesRegex(ac.LimiteAzureError, "429"):
                client.create(messages=[{"content": "test"}])
            self.assertEqual(create.call_count, 2)
            sleep.assert_called_once_with(2)

if __name__ == "__main__": unittest.main()
