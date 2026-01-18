import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add parent directory to path to import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_orchestrator

class TestAIProvider(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('asyncio.create_subprocess_exec')
    def test_ollama_ask_success(self, mock_exec):
        # Setup mock process
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Ollama output", b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        provider = ai_orchestrator.OllamaProvider()
        response = self.loop.run_until_complete(provider.ask("hello"))

        self.assertEqual(response.provider_name, "ollama")
        self.assertEqual(response.content, "Ollama output")
        self.assertIsNone(response.error)

    @patch('asyncio.create_subprocess_exec')
    def test_gemini_ask_cleanup(self, mock_exec):
        # Gemini often outputs "YOLO mode" lines we want to clean
        raw_output = b"YOLO mode active\nActual answer\nLoaded cached..."
        
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(raw_output, b""))
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        provider = ai_orchestrator.GeminiProvider()
        response = self.loop.run_until_complete(provider.ask("hello"))

        self.assertEqual(response.content, "Actual answer")

    @patch('asyncio.create_subprocess_exec')
    def test_provider_failure(self, mock_exec):
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Some error occurred"))
        mock_process.returncode = 1
        mock_exec.return_value = mock_process

        provider = ai_orchestrator.ClaudeProvider()
        response = self.loop.run_until_complete(provider.ask("hello"))

        self.assertEqual(response.content, "")
        self.assertEqual(response.error, "Some error occurred")


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_get_provider(self):
        p1 = ai_orchestrator.OllamaProvider()
        orch = ai_orchestrator.Orchestrator([p1])
        self.assertEqual(orch.get_provider("ollama"), p1)
        self.assertIsNone(orch.get_provider("missing"))

    def test_run_parallel(self):
        # Mock providers
        p1 = MagicMock(spec=ai_orchestrator.AIProvider)
        p1.name = "p1"
        p1.ask = AsyncMock(return_value=ai_orchestrator.ProviderResponse("p1", "res1"))

        p2 = MagicMock(spec=ai_orchestrator.AIProvider)
        p2.name = "p2"
        p2.ask = AsyncMock(return_value=ai_orchestrator.ProviderResponse("p2", "res2"))

        orch = ai_orchestrator.Orchestrator([p1, p2])
        
        results = self.loop.run_until_complete(orch.run_parallel("prompt", ["p1", "p2"]))
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results["p1"].content, "res1")
        self.assertEqual(results["p2"].content, "res2")

if __name__ == '__main__':
    unittest.main()
