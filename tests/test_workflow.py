import asyncio
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

# Add parent directory to path to import the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ai_orchestrator


class TestWorkflow(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.output_dir = Path("test_output")

    def tearDown(self):
        self.loop.close()
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_workflow_happy_path(self):
        # Mock providers
        planner = MagicMock(spec=ai_orchestrator.AIProvider)
        planner.name = "claude"
        planner.is_available.return_value = True
        planner.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("claude", "1. Step 1")
        )

        coder = MagicMock(spec=ai_orchestrator.AIProvider)
        coder.name = "gemini"
        coder.is_available.return_value = True
        # First call: Initial code, Second call: Refined code (if needed)
        coder.ask = AsyncMock(
            side_effect=[
                ai_orchestrator.ProviderResponse("gemini", "print('hello')"),
                ai_orchestrator.ProviderResponse("gemini", "print('hello world')"),
            ]
        )

        tester = MagicMock(spec=ai_orchestrator.AIProvider)
        tester.name = "ollama"
        tester.is_available.return_value = True
        tester.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse(
                "ollama", "def test_hello(): pass"
            )
        )

        reviewer = MagicMock(spec=ai_orchestrator.AIProvider)
        reviewer.name = "claude"
        reviewer.is_available.return_value = True
        reviewer.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("claude", "LGTM")
        )

        documenter = MagicMock(spec=ai_orchestrator.AIProvider)
        documenter.name = "gemini"
        documenter.is_available.return_value = True
        documenter.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("gemini", "# README")
        )

        orch = ai_orchestrator.Orchestrator(
            [planner, coder, tester, reviewer, documenter]
        )

        # Run workflow
        self.loop.run_until_complete(
            ai_orchestrator.mode_workflow(
                orch, "Make a generic thing", str(self.output_dir)
            )
        )

        # Check output files
        self.assertTrue((self.output_dir / "1_plan.txt").exists())
        self.assertTrue((self.output_dir / "2_code.txt").exists())
        self.assertTrue((self.output_dir / "3_tests.txt").exists())
        self.assertTrue((self.output_dir / "4_review.txt").exists())
        self.assertTrue((self.output_dir / "5_final_code.txt").exists())
        self.assertTrue((self.output_dir / "6_README.md").exists())

    def test_workflow_partial_failure(self):
        # Planner succeeds, Coder fails
        planner = MagicMock(spec=ai_orchestrator.AIProvider)
        planner.name = "claude"
        planner.is_available.return_value = True
        planner.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("claude", "1. Step 1")
        )

        coder = MagicMock(spec=ai_orchestrator.AIProvider)
        coder.name = "gemini"
        coder.is_available.return_value = True
        coder.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse(
                "gemini", "", error="API Error"
            )
        )

        # Others might exist but shouldn't be called if coder fails
        tester = MagicMock(spec=ai_orchestrator.AIProvider)
        tester.name = "ollama"
        tester.is_available.return_value = True

        orch = ai_orchestrator.Orchestrator([planner, coder, tester])

        self.loop.run_until_complete(
            ai_orchestrator.mode_workflow(
                orch, "Make a generic thing", str(self.output_dir)
            )
        )

        # Plan should exist, Code shouldn't (or should be empty/error logged, but here we check files)
        self.assertTrue((self.output_dir / "1_plan.txt").exists())
        self.assertFalse((self.output_dir / "2_code.txt").exists())

    def test_workflow_refinement_logic(self):
        """Test that refinement is triggered when review is not LGTM."""
        planner = MagicMock(spec=ai_orchestrator.AIProvider)
        planner.name = "planner"
        planner.is_available.return_value = True
        planner.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("p", "plan")
        )

        coder = MagicMock(spec=ai_orchestrator.AIProvider)
        coder.name = "coder"
        coder.is_available.return_value = True
        # 1. Initial code, 2. Refined code
        coder.ask = AsyncMock(
            side_effect=[
                ai_orchestrator.ProviderResponse("coder", "Bad Code"),
                ai_orchestrator.ProviderResponse("coder", "Fixed Code"),
            ]
        )

        tester = MagicMock(spec=ai_orchestrator.AIProvider)
        tester.name = "tester"
        tester.is_available.return_value = True
        tester.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("t", "tests")
        )

        reviewer = MagicMock(spec=ai_orchestrator.AIProvider)
        reviewer.name = "reviewer"
        reviewer.is_available.return_value = True
        reviewer.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse(
                "r", "Critical issue: Syntax error"
            )
        )

        documenter = MagicMock(spec=ai_orchestrator.AIProvider)
        documenter.name = "documenter"
        documenter.is_available.return_value = True
        documenter.ask = AsyncMock(
            return_value=ai_orchestrator.ProviderResponse("d", "doc")
        )

        orch = ai_orchestrator.Orchestrator(
            [planner, coder, tester, reviewer, documenter]
        )

        self.loop.run_until_complete(
            ai_orchestrator.mode_workflow(orch, "Fix code", str(self.output_dir))
        )

        # Verify coder called twice
        self.assertEqual(coder.ask.call_count, 2)

        # Verify second call included the review feedback
        second_call_args = coder.ask.call_args_list[1]
        prompt_arg = second_call_args[0][0]
        self.assertIn("Critical issue: Syntax error", prompt_arg)
        self.assertIn("Bad Code", prompt_arg)

        # Verify final code file has fixed code
        final_code = (self.output_dir / "5_final_code.txt").read_text()
        self.assertEqual(final_code, "Fixed Code")

    def test_workflow_timeout(self):
        """Test workflow timeout handling."""
        # Create a mock provider that sleeps longer than the timeout
        slow_planner = MagicMock(spec=ai_orchestrator.AIProvider)
        slow_planner.name = "slow_poke"
        slow_planner.is_available.return_value = True

        async def slow_ask(prompt):
            await asyncio.sleep(2)  # Sleep 2 seconds
            return ai_orchestrator.ProviderResponse("slow_poke", "plan")

        slow_planner.ask = AsyncMock(side_effect=slow_ask)

        # We need enough providers to start workflow
        dummy1 = MagicMock(spec=ai_orchestrator.AIProvider)
        dummy1.name = "dummy1"
        dummy1.is_available.return_value = True

        dummy2 = MagicMock(spec=ai_orchestrator.AIProvider)
        dummy2.name = "dummy2"
        dummy2.is_available.return_value = True

        dummy3 = MagicMock(spec=ai_orchestrator.AIProvider)
        dummy3.name = "dummy3"
        dummy3.is_available.return_value = True

        dummy4 = MagicMock(spec=ai_orchestrator.AIProvider)
        dummy4.name = "dummy4"
        dummy4.is_available.return_value = True

        orch = ai_orchestrator.Orchestrator(
            [slow_planner, dummy1, dummy2, dummy3, dummy4]
        )

        # Set a very short timeout (0.1s)
        # Note: We can't easily change the hardcoded multiplier in mode_workflow without injecting args,
        # but mode_workflow is called by main logic usually.
        # Here we are calling mode_workflow directly.
        # mode_workflow does NOT handle the timeout itself; main_async does.
        # So we must verify that main_async handles the timeout, OR verify that if we wrap mode_workflow it times out.
        # The requirement was "Added asyncio.wait_for to handle overall workflow timeouts".
        # Let's test the wrapping logic which is in main_async, but that's hard to test directly.
        # Instead, we will wrap mode_workflow here just like main_async does.

        async def run_with_timeout():
            await asyncio.wait_for(
                ai_orchestrator.mode_workflow(orch, "test"), timeout=0.1
            )

        with self.assertRaises(asyncio.TimeoutError):
            self.loop.run_until_complete(run_with_timeout())


if __name__ == "__main__":
    unittest.main()
