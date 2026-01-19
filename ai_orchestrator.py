#!/usr/bin/env python3
"""
AI Orchestrator - Multi-provider AI workflow automation tool.

Integrates Ollama, Claude, and Gemini providers into unified workflows.
"""

import argparse
import asyncio
import json
import logging
import os
import shutil
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from security_validation import (
    InvalidInputError,
    safe_decode,
    sanitize_ai_response,
    sanitize_log_message,
    validate_output_path,
    validate_prompt,
)

# --- Configuration & Constants ---
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:480b-cloud")
DEFAULT_TIMEOUT = 900  # seconds (15 minutes for long-running operations)
ANSI_BOLD = "\033[1m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_CYAN = "\033[36m"
ANSI_YELLOW = "\033[33m"
ANSI_BLUE = "\033[34m"
ANSI_RESET = "\033[0m"


@dataclass
class ProviderResponse:
    provider_name: str
    content: str
    error: Optional[str] = None
    duration: float = 0.0
    is_quota_error: bool = False
    is_retryable: bool = True


# --- Error Classification Helper ---
def classify_error(error_message: str) -> Tuple[bool, bool]:
    """
    Classify error to determine if it's a quota error and if it's retryable.

    Returns:
        Tuple[is_quota_error, is_retryable]
    """
    if not error_message:
        return False, True

    error_lower = error_message.lower()

    # Check for quota/rate limit errors
    quota_indicators = [
        "quota",
        "exhausted",
        "capacity",
        "rate limit",
        "429",
        "too many requests",
        "terminalquotaerror",
        "empty response",
    ]

    is_quota = any(indicator in error_lower for indicator in quota_indicators)

    # Quota errors should not be retried (they need time to reset)
    # Other errors (timeouts, network issues) can be retried
    is_retryable = not is_quota

    return is_quota, is_retryable


# --- Abstract Base Class for Providers ---
class AIProvider(ABC):
    def __init__(self, name: str, timeout: int = DEFAULT_TIMEOUT):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    async def ask(self, prompt: str) -> ProviderResponse:
        pass

    def is_available(self) -> bool:
        """Check if the underlying CLI tool is available."""
        return shutil.which(self._get_binary_name()) is not None

    @abstractmethod
    def _get_binary_name(self) -> str:
        pass

    def _validate_prompt(self, prompt: str):
        """Basic input validation to prevent issues."""
        try:
            return validate_prompt(prompt, min_length=1, max_length=4000)
        except InvalidInputError as e:
            raise ValueError(f"Invalid prompt: {e}")
        # Subprocess.run/exec handles argument separation, preventing standard shell injection.


# --- Concrete Provider Implementations ---
class OllamaProvider(AIProvider):
    def __init__(self, model: str = DEFAULT_OLLAMA_MODEL, **kwargs):
        super().__init__("ollama", **kwargs)
        self.model = model

    def _get_binary_name(self) -> str:
        return "ollama"

    async def ask(self, prompt: str) -> ProviderResponse:
        try:
            self._validate_prompt(prompt)
            if not self.is_available():
                return ProviderResponse(
                    self.name, "", error="Provider unavailable (binary not found)"
                )

            logging.info(f"[{self.name}] sending request (model={self.model})...")
            print(
                f"{ANSI_BLUE}⏳ [{self.name}] Sending request with model {self.model}... (timeout: {self.timeout}s){ANSI_RESET}"
            )
            start_time = time.time()
            print(
                f"{ANSI_CYAN}   Started at: {time.strftime('%H:%M:%S', time.localtime(start_time))}{ANSI_RESET}"
            )

            # ollama run <model> <prompt>
            process = await asyncio.create_subprocess_exec(
                "ollama",
                "run",
                self.model,
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
            duration = time.time() - start_time
            print(f"{ANSI_CYAN}   Completed in: {duration:.1f}s{ANSI_RESET}")

            if process.returncode != 0:
                error_msg = safe_decode(stderr, errors="replace").strip()
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )

            # Check if response is empty (can happen with quota errors)
            content = safe_decode(stdout, errors="replace").strip()
            if not content:
                error_msg = safe_decode(stderr, errors="replace").strip()
                if not error_msg:
                    error_msg = "Empty response received from provider (possible quota limit or error)"
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )

            # Sanitize AI response before returning
            sanitized_content = sanitize_ai_response(content, max_length=100000)
            return ProviderResponse(self.name, sanitized_content, duration=duration)
        except ValueError as ve:
            error_msg = str(ve)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=0.0,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )
        except asyncio.TimeoutError:
            return ProviderResponse(
                self.name,
                "",
                error="Timeout exceeded",
                duration=time.time() - start_time,
                is_quota_error=False,
                is_retryable=True,
            )
        except Exception as e:
            error_msg = str(e)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=time.time() - start_time,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )


class ClaudeProvider(AIProvider):
    def __init__(self, **kwargs):
        super().__init__("claude", **kwargs)

    def _get_binary_name(self) -> str:
        return "claude"

    async def ask(self, prompt: str) -> ProviderResponse:
        try:
            self._validate_prompt(prompt)
            if not self.is_available():
                return ProviderResponse(
                    self.name, "", error="Provider unavailable (binary not found)"
                )

            logging.info(f"[{self.name}] sending request...")
            print(
                f"{ANSI_BLUE}⏳ [{self.name}] Sending request... (timeout: {self.timeout}s){ANSI_RESET}"
            )
            start_time = time.time()
            print(
                f"{ANSI_CYAN}   Started at: {time.strftime('%H:%M:%S', time.localtime(start_time))}{ANSI_RESET}"
            )

            # claude -p <prompt>
            process = await asyncio.create_subprocess_exec(
                "claude",
                "-p",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
            duration = time.time() - start_time
            print(f"{ANSI_CYAN}   Completed in: {duration:.1f}s{ANSI_RESET}")

            if process.returncode != 0:
                error_msg = safe_decode(stderr, errors="replace").strip()
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )

            # Check if response is empty (can happen with quota errors)
            content = safe_decode(stdout, errors="replace").strip()
            if not content:
                # Check stderr for error message
                error_msg = safe_decode(stderr, errors="replace").strip()
                if not error_msg:
                    error_msg = "Empty response received from provider (possible quota limit or error)"
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )

            # Sanitize AI response before returning
            sanitized_content = sanitize_ai_response(content, max_length=100000)
            return ProviderResponse(self.name, sanitized_content, duration=duration)
        except ValueError as ve:
            error_msg = str(ve)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=0.0,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )
        except asyncio.TimeoutError:
            return ProviderResponse(
                self.name,
                "",
                error="Timeout exceeded",
                duration=time.time() - start_time,
                is_quota_error=False,
                is_retryable=True,
            )
        except Exception as e:
            error_msg = str(e)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=time.time() - start_time,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )


class GeminiProvider(AIProvider):
    def __init__(self, **kwargs):
        super().__init__("gemini", **kwargs)

    def _get_binary_name(self) -> str:
        return "gemini"

    async def ask(self, prompt: str) -> ProviderResponse:
        try:
            self._validate_prompt(prompt)
            if not self.is_available():
                return ProviderResponse(
                    self.name, "", error="Provider unavailable (binary not found)"
                )

            logging.info(f"[{self.name}] sending request...")
            print(
                f"{ANSI_BLUE}⏳ [{self.name}] Sending request... (timeout: {self.timeout}s){ANSI_RESET}"
            )
            start_time = time.time()
            print(
                f"{ANSI_CYAN}   Started at: {time.strftime('%H:%M:%S', time.localtime(start_time))}{ANSI_RESET}"
            )

            # gemini <prompt> --yolo
            process = await asyncio.create_subprocess_exec(
                "gemini",
                prompt,
                "--yolo",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )
            duration = time.time() - start_time
            print(f"{ANSI_CYAN}   Completed in: {duration:.1f}s{ANSI_RESET}")

            if process.returncode != 0:
                error_msg = safe_decode(stderr, errors="replace").strip()
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )

            output = safe_decode(stdout, errors="replace")

            # Check if response is empty before cleanup (can happen with quota errors)
            if not output.strip():
                error_msg = safe_decode(stderr, errors="replace").strip()
                if not error_msg:
                    error_msg = "Empty response received from provider (possible quota limit or error)"
                is_quota, is_retryable = classify_error(error_msg)
                return ProviderResponse(
                    self.name,
                    "",
                    error=error_msg,
                    duration=duration,
                    is_quota_error=is_quota,
                    is_retryable=is_retryable,
                )
            # Cleanup specific to previous script logic
            cleaned_lines = [
                line
                for line in output.splitlines()
                if "YOLO mode" not in line and "Loaded cached" not in line
            ]
            content = "\n".join(cleaned_lines).strip()
            # Sanitize AI response before returning
            sanitized_content = sanitize_ai_response(content, max_length=100000)
            return ProviderResponse(self.name, sanitized_content, duration=duration)
        except ValueError as ve:
            error_msg = str(ve)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=0.0,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )
        except asyncio.TimeoutError:
            return ProviderResponse(
                self.name,
                "",
                error="Timeout exceeded",
                duration=time.time() - start_time,
                is_quota_error=False,
                is_retryable=True,
            )
        except Exception as e:
            error_msg = str(e)
            is_quota, is_retryable = classify_error(error_msg)
            return ProviderResponse(
                self.name,
                "",
                error=error_msg,
                duration=time.time() - start_time,
                is_quota_error=is_quota,
                is_retryable=is_retryable,
            )


# --- Orchestrator Logic ---


class Orchestrator:
    def __init__(self, providers: List[AIProvider]):
        # Handle multiple providers with same name by adding suffix
        self.providers = {}
        name_counts = {}
        for p in providers:
            if p.name in name_counts:
                name_counts[p.name] += 1
                # Add suffix for duplicate names (e.g., ollama_fallback)
                key = (
                    f"{p.name}_fallback"
                    if name_counts[p.name] == 2
                    else f"{p.name}_{name_counts[p.name]}"
                )
                self.providers[key] = p
            else:
                name_counts[p.name] = 1
                self.providers[p.name] = p

    def get_provider(self, name: str) -> Optional[AIProvider]:
        return self.providers.get(name)

    async def run_parallel(
        self, prompt: str, provider_names: List[str]
    ) -> Dict[str, ProviderResponse]:
        logging.info(
            f"Orchestrator starting parallel run for: {', '.join(provider_names)}"
        )
        tasks = []
        for name in provider_names:
            provider = self.get_provider(name)
            if provider:
                tasks.append(provider.ask(prompt))
            else:
                print(f"Warning: Provider '{name}' not found.")

        results = await asyncio.gather(*tasks)
        return {res.provider_name: res for res in results}


# --- UI Helpers --- (moved to top for early availability)


def print_header(text: str):
    print(f"\n{ANSI_BOLD}{ANSI_CYAN}=== {text} ==={ANSI_RESET}")


def print_result(response: ProviderResponse):
    print(
        f"\n{ANSI_BOLD}--- Response from {response.provider_name.upper()} ({response.duration:.2f}s) ---"
    )
    if response.error:
        print(f"{ANSI_RED}Error: {response.error}{ANSI_RESET}")
    else:
        print(response.content)


# --- Retry and Fallback Helpers ---


async def retry_with_backoff(
    provider: AIProvider, prompt: str, max_retries: int = 3, base_delay: float = 2.0
) -> ProviderResponse:
    """
    Retry a provider request with exponential backoff.
    Skips retries for quota errors (they need time to reset).
    """
    response = await provider.ask(prompt)

    # If successful or quota error (not retryable), return immediately
    if not response.error or response.is_quota_error:
        return response

    # Retry logic for retryable errors
    attempt = 0
    while attempt < max_retries and response.error and response.is_retryable:
        attempt += 1
        delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
        logging.warning(
            f"[{provider.name}] Retry {attempt}/{max_retries} after {delay}s delay..."
        )
        print(
            f"{ANSI_YELLOW}🔄 [{provider.name}] Retry {attempt}/{max_retries} after {delay:.1f}s delay...{ANSI_RESET}"
        )
        print(f"{ANSI_YELLOW}   Error encountered: {response.error[:150]}{ANSI_RESET}")
        print(f"{ANSI_YELLOW}   Waiting {delay:.1f}s before retry...{ANSI_RESET}")
        await asyncio.sleep(delay)
        print(f"{ANSI_CYAN}   Retrying now...{ANSI_RESET}")
        response = await provider.ask(prompt)

        if not response.error:
            print(
                f"{ANSI_GREEN}✓ [{provider.name}] Retry successful after {attempt} attempt(s){ANSI_RESET}"
            )

        if not response.error:
            break

    return response


async def ask_with_fallback(
    orchestrator: Orchestrator,
    provider_priority: List[str],
    prompt: str,
    role_name: str,
) -> ProviderResponse:
    """
    Try providers in priority order with fallback support.
    If a provider fails with quota error, immediately try the next one.
    For other errors, retry with backoff before trying next provider.
    """
    attempted_providers = []

    for provider_name in provider_priority:
        provider = orchestrator.get_provider(provider_name)

        # Skip unavailable providers
        if not provider or not provider.is_available():
            continue

        attempted_providers.append(provider_name)
        logging.info(f"[{role_name}] Trying {provider_name}...")
        print(f"\n{ANSI_CYAN}{'─' * 60}{ANSI_RESET}")

        # Special message for fallback local model
        if provider_name == "ollama_fallback":
            print(
                f"{ANSI_YELLOW}⚠️  [{role_name}] All primary providers failed. Using last resort fallback: qwen3-coder:30b (local){ANSI_RESET}"
            )
        else:
            print(f"{ANSI_CYAN}🔍 [{role_name}] Trying {provider_name}...{ANSI_RESET}")

        print(f"{ANSI_CYAN}{'─' * 60}{ANSI_RESET}")

        # Try with retry/backoff
        step_start = time.time()
        response = await retry_with_backoff(provider, prompt)
        step_duration = time.time() - step_start

        # Success - but double-check content is not empty!
        if not response.error:
            # Additional safeguard: treat empty content as an error
            if not response.content or not response.content.strip():
                logging.warning(
                    f"[{role_name}] {provider_name} returned empty response despite no error flag"
                )
                print(
                    f"{ANSI_RED}⚠ [{role_name}] {provider_name} returned empty response (possible quota limit). Falling back to next provider...{ANSI_RESET}"
                )
                # Treat as quota error and continue to next provider
                continue

            duration_msg = (
                f"(request: {response.duration:.1f}s, total: {step_duration:.1f}s)"
            )
            if len(attempted_providers) > 1:
                logging.info(
                    f"[{role_name}] ✓ Successfully fell back to {provider_name}"
                )
                # Special success message for fallback
                if provider_name == "ollama_fallback":
                    print(
                        f"\n{ANSI_GREEN}✅ [{role_name}] Fallback local model (qwen3-coder:30b) succeeded {duration_msg}{ANSI_RESET}"
                    )
                else:
                    print(
                        f"\n{ANSI_GREEN}✅ [{role_name}] Successfully fell back to {provider_name} {duration_msg}{ANSI_RESET}"
                    )
            else:
                print(
                    f"\n{ANSI_GREEN}✅ [{role_name}] Completed with {provider_name} {duration_msg}{ANSI_RESET}"
                )
            print(
                f"{ANSI_GREEN}   Response length: {len(response.content)} characters{ANSI_RESET}"
            )
            return response

        # Handle errors
        if response.is_quota_error:
            logging.warning(
                f"[{role_name}] {provider_name} quota exhausted, falling back to next provider..."
            )
            print(
                f"{ANSI_RED}⚠ [{role_name}] {provider_name} quota exhausted. Falling back to next provider...{ANSI_RESET}"
            )
        else:
            logging.warning(f"[{role_name}] {provider_name} failed: {response.error}")
            error_preview = response.error[:150] if response.error else "Unknown error"
            print(
                f"{ANSI_RED}⚠ [{role_name}] {provider_name} failed: {error_preview}{ANSI_RESET}"
            )

    # All providers failed
    error_msg = f"All providers failed for {role_name}. Attempted: {', '.join(attempted_providers)}"
    return ProviderResponse("none", "", error=error_msg, duration=0.0)


# --- Main Modes ---


async def mode_panel(orchestrator: Orchestrator, prompt: str, curator_name: str):
    print_header(f"🚀 Starting Panel Mode (Curator: {curator_name})")

    # 1. Identify workers (everyone except curator)
    workers = [name for name in orchestrator.providers.keys() if name != curator_name]

    if not workers:
        print(f"{ANSI_RED}Error: No workers available for panel.{ANSI_RESET}")
        return

    print(f"Workers: {', '.join(workers)}")
    print("Gathering drafts concurrently...")

    # 2. Parallel execution
    results = await orchestrator.run_parallel(prompt, workers)

    # 3. Compile drafts
    drafts_text = ""
    for name, res in results.items():
        if res.error:
            print(f"{ANSI_RED}[{name}] failed: {res.error}{ANSI_RESET}")
        else:
            print(f"{ANSI_GREEN}[{name}] finished in {res.duration:.2f}s.{ANSI_RESET}")
            drafts_text += f"--- DRAFT FROM {name.upper()} ---\n{res.content}\n\n"

    if not drafts_text:
        print(f"{ANSI_RED}No valid drafts received. Aborting curation.{ANSI_RESET}")
        return

    # 4. Curation
    curation_prompt = (
        f"You are the Chief Editor and Curator. I have a user request and several draft answers from different AI models.\n"
        f"Your goal is to synthesize a single, perfect response. \n"
        f"Analyze the drafts for accuracy, completeness, and clarity. Fix any errors.\n\n"
        f"ORIGINAL USER REQUEST: '{prompt}'\n\n"
        f"{drafts_text}"
        "--- END OF DRAFTS ---\n"
        "Please provide the final, synthesized answer below. Do not just list the drafts; create a cohesive response."
    )

    print(f"\n[Curator: {curator_name}] is synthesizing...")
    curator = orchestrator.get_provider(curator_name)
    if not curator:
        print(f"Error: Curator {curator_name} not found.")
        return

    final_res = await curator.ask(curation_prompt)

    print_header("FINAL CURATED ANSWER")
    if final_res.error:
        print(f"{ANSI_RED}Curator failed: {final_res.error}{ANSI_RESET}")
    else:
        print(final_res.content)
    print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")


async def mode_smart(orchestrator: Orchestrator, prompt: str):
    # Ask Ollama first
    ollama = orchestrator.get_provider("ollama")
    claude = orchestrator.get_provider("claude")

    if not ollama or not claude:
        print("Error: Smart mode requires both 'ollama' and 'claude'.")
        return

    print("1. Asking Ollama...")
    ollama_res = await ollama.ask(prompt)
    print_result(ollama_res)

    if ollama_res.error:
        print("Ollama failed, skipping verification.")
        return

    print("\n2. Asking Claude to verify...")
    verification_prompt = (
        f"I asked a local AI this prompt: '{prompt}'\n"
        f"It gave this answer:\n{ollama_res.content}\n"
        f"Is this answer correct and complete? If not, please correct it."
    )
    claude_res = await claude.ask(verification_prompt)
    print_result(claude_res)


async def mode_workflow(
    orchestrator: Orchestrator, prompt: str, output_dir: Optional[str] = None
):
    print_header("⚙️ Starting Autonomous Robust Workflow Mode")

    # 1. Role Assignment Strategy with Fallback Support
    # Last resort: ollama_fallback (qwen3-coder:30b) used only when all else fails
    role_priorities = {
        "planner": ["claude", "gemini", "ollama", "ollama_fallback"],
        "coder": ["gemini", "claude", "ollama", "ollama_fallback"],
        "tester": ["gemini", "claude", "ollama", "ollama_fallback"],
        "reviewer": ["claude", "ollama", "gemini", "ollama_fallback"],
        "documenter": ["ollama", "gemini", "claude", "ollama_fallback"],
    }

    # Verify at least one provider is available for each role
    for role, priorities in role_priorities.items():
        has_available = any(
            orchestrator.get_provider(name)
            and orchestrator.get_provider(name).is_available()
            for name in priorities
        )
        if not has_available:
            print(
                f"{ANSI_RED}Error: No available providers for role '{role}'.{ANSI_RESET}"
            )
            return

    print(f"{ANSI_BOLD}Team Roles with Fallback:{ANSI_RESET}")
    print(f"  • 🧠 Planner:    {' → '.join(role_priorities['planner'])}")
    print(f"  • 💻 Coder:      {' → '.join(role_priorities['coder'])}")
    print(f"  • 🧪 Tester:     {' → '.join(role_priorities['tester'])}")
    print(f"  • 🔍 Reviewer:   {' → '.join(role_priorities['reviewer'])}")
    print(f"  • 📝 Documenter: {' → '.join(role_priorities['documenter'])}")
    print(
        f"\n{ANSI_CYAN}ℹ️  Last resort fallback: ollama_fallback (qwen3-coder:30b){ANSI_RESET}"
    )

    # Setup persistence with security validation
    out_path = None
    if output_dir:
        try:
            out_path = validate_output_path(
                Path(output_dir), Path.cwd(), allow_creation=True
            )
            print(f"📂 Output directory: {out_path}")
        except Exception as e:
            print(f"{ANSI_YELLOW}⚠ Path validation failed: {e}{ANSI_RESET}")
            print(f"{ANSI_YELLOW}⚠ Continuing without file output{ANSI_RESET}")
            out_path = None

    try:
        # --- Step 1: Planning ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[1/6] 🧠 Generating Plan...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        plan_prompt = (
            f"Role: Senior Software Architect.\n"
            f"Task: Create a concise, step-by-step technical implementation plan for: '{prompt}'.\n"
            f"Output: Numbered list of steps only. Focus on architecture and edge cases."
        )
        plan_res = await ask_with_fallback(
            orchestrator, role_priorities["planner"], plan_prompt, "Planner"
        )
        if plan_res.error:
            print(f"{ANSI_RED}❌ Planning failed: {plan_res.error}{ANSI_RESET}")
            return

        if out_path:
            (out_path / "1_plan.txt").write_text(plan_res.content)

        print(
            f"\n{ANSI_GREEN}✅ Plan generated by {plan_res.provider_name} (Duration: {plan_res.duration:.1f}s){ANSI_RESET}"
        )
        print(f"{ANSI_BOLD}\n--- PLAN OUTPUT ---{ANSI_RESET}")
        print(f"{ANSI_CYAN}{plan_res.content}{ANSI_RESET}")

        # --- Step 2: Coding ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[2/6] 💻 Writing Initial Code...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        code_prompt = (
            f"Role: Senior Developer.\n"
            f"Task: Write the code based strictly on this plan.\n"
            f"Plan:\n{plan_res.content}\n\n"
            f"Output: The code block(s) only. Minimal explanation."
        )
        code_res = await ask_with_fallback(
            orchestrator, role_priorities["coder"], code_prompt, "Coder"
        )
        if code_res.error:
            print(f"{ANSI_RED}❌ Coding failed: {code_res.error}{ANSI_RESET}")
            return

        if out_path:
            (out_path / "2_code.txt").write_text(code_res.content)

        print(
            f"\n{ANSI_GREEN}✅ Initial code generated by {code_res.provider_name} (Duration: {code_res.duration:.1f}s){ANSI_RESET}"
        )
        print(f"{ANSI_BOLD}\n--- CODE OUTPUT (First 500 chars) ---{ANSI_RESET}")
        print(f"{ANSI_CYAN}{code_res.content[:500]}...{ANSI_RESET}")

        # --- Step 3: Test Generation ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[3/6] 🧪 Generating Tests...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        test_prompt = (
            f"Role: QA Engineer.\n"
            f"Task: Write a comprehensive unit test suite (e.g., using pytest/unittest) for the following code.\n"
            f"Code:\n{code_res.content}\n\n"
            f"Output: The test code block(s) only."
        )
        test_res = await ask_with_fallback(
            orchestrator, role_priorities["tester"], test_prompt, "Tester"
        )
        if test_res.error:
            print(f"{ANSI_RED}❌ Testing failed: {test_res.error}{ANSI_RESET}")
            print(f"{ANSI_YELLOW}⚠ Continuing without tests...{ANSI_RESET}")
            # Non-blocking failure
        else:
            if out_path:
                (out_path / "3_tests.txt").write_text(test_res.content)
            print(
                f"\n{ANSI_GREEN}✅ Tests generated by {test_res.provider_name} (Duration: {test_res.duration:.1f}s){ANSI_RESET}"
            )
            print(f"{ANSI_BOLD}\n--- TEST OUTPUT (First 500 chars) ---{ANSI_RESET}")
            print(f"{ANSI_CYAN}{test_res.content[:500]}...{ANSI_RESET}")

        # --- Step 4: Reviewing ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[4/6] 🔍 Reviewing Code & Tests...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")

        # Prepare content for review, handling cases where tests failed
        tests_content = (
            test_res.content
            if not test_res.error
            else "Tests unavailable due to generation error."
        )

        review_prompt = (
            f"Role: Lead Developer.\n"
            f"Task: Review the Code and Tests for bugs, security issues, and coverage gaps.\n"
            f"Code:\n{code_res.content}\n\n"
            f"Tests:\n{tests_content}\n\n"
            f"Output: A structured list of critical issues to fix. If none, say 'LGTM'."
        )
        review_res = await ask_with_fallback(
            orchestrator, role_priorities["reviewer"], review_prompt, "Reviewer"
        )

        if out_path:
            (out_path / "4_review.txt").write_text(review_res.content)

        print(
            f"\n{ANSI_GREEN}✅ Review completed by {review_res.provider_name} (Duration: {review_res.duration:.1f}s){ANSI_RESET}"
        )
        print(f"{ANSI_BOLD}\n--- REVIEW FINDINGS ---{ANSI_RESET}")
        print(f"{ANSI_CYAN}{review_res.content}{ANSI_RESET}")

        # --- Step 5: Refinement ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[5/6] ✨ Refining Implementation...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")

        # Robust LGTM check
        import re

        is_lgtm = bool(re.search(r"\bLGTM\b", review_res.content, re.IGNORECASE))

        if is_lgtm and len(review_res.content) < 200:
            print(
                f"\n{ANSI_GREEN}✅ No critical issues found. Skipping refinement.{ANSI_RESET}"
            )
            final_code = code_res.content
        else:
            refine_prompt = (
                f"Role: Senior Developer.\n"
                f"Task: Synthesize the Final Version. Fix issues identified in the review.\n"
                f"Original Code:\n{code_res.content}\n"
                f"Review Feedback:\n{review_res.content}\n\n"
                f"Output: Provide ONLY the final corrected code block."
            )
            refined_code_res = await ask_with_fallback(
                orchestrator, role_priorities["coder"], refine_prompt, "Coder"
            )
            if refined_code_res.error:
                print(
                    f"{ANSI_RED}❌ Refinement failed: {refined_code_res.error}{ANSI_RESET}"
                )
                print(f"{ANSI_YELLOW}⚠ Using original code as fallback{ANSI_RESET}")
                final_code = code_res.content  # Fallback
            else:
                final_code = refined_code_res.content
                print(
                    f"\n{ANSI_GREEN}✅ Code refined by {refined_code_res.provider_name} (Duration: {refined_code_res.duration:.1f}s){ANSI_RESET}"
                )
                print(
                    f"{ANSI_BOLD}\n--- REFINED CODE (First 500 chars) ---{ANSI_RESET}"
                )
                print(f"{ANSI_CYAN}{final_code[:500]}...{ANSI_RESET}")

        if out_path:
            (out_path / "5_final_code.txt").write_text(final_code)

        # --- Step 6: Documentation ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_BOLD}[6/6] 📝 Writing Documentation...{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        doc_prompt = (
            f"Role: Technical Writer.\n"
            f"Task: Create a brief README.md content for this code.\n"
            f"Context: {prompt}\n"
            f"Final Code:\n{final_code}\n\n"
            f"Output: Markdown formatted text."
        )
        doc_res = await ask_with_fallback(
            orchestrator, role_priorities["documenter"], doc_prompt, "Documenter"
        )

        if doc_res.error:
            print(f"{ANSI_RED}❌ Documentation failed: {doc_res.error}{ANSI_RESET}")
        else:
            if out_path:
                try:
                    (out_path / "6_README.md").write_text(doc_res.content)
                except Exception as e:
                    print(f"{ANSI_RED}Failed to save README: {e}{ANSI_RESET}")
            print(
                f"\n{ANSI_GREEN}✅ Documentation written by {doc_res.provider_name} (Duration: {doc_res.duration:.1f}s){ANSI_RESET}"
            )

        # --- Final Output ---
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print_header("🎉 FINAL DELIVERABLE")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")
        print(f"{ANSI_BOLD}--- FINAL CODE ---{ANSI_RESET}")
        print(final_code)
        if not test_res.error:
            print(f"\n{ANSI_BOLD}--- TESTS ---")
            print(test_res.content)

        print(f"\n{ANSI_BOLD}--- DOCUMENTATION ---")
        if doc_res.error:
            print(f"{ANSI_RED}(Missing due to error){ANSI_RESET}")
        else:
            print(doc_res.content)

        print(f"\n{ANSI_BOLD}--- REVIEW NOTES ---")
        print(review_res.content)
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")

    except Exception as e:
        print(f"{ANSI_RED}Workflow crashed: {e}{ANSI_RESET}")


async def main_async():
    parser = argparse.ArgumentParser(description="AI Orchestrator - Workflow Mode Only")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send (optional, will be requested if not provided)",
    )
    parser.add_argument(
        "--output-dir", help="Directory to save workflow results", default=None
    )
    args = parser.parse_args()

    # Get prompt interactively if not provided
    if not args.prompt:
        print(f"{ANSI_BOLD}{ANSI_CYAN}AI Orchestrator - Workflow Mode{ANSI_RESET}")
        print("Enter your prompt (minimum 10 characters):")
        args.prompt = input("> ").strip()

    # Validate prompt
    if len(args.prompt) < 10:
        print(
            f"{ANSI_RED}Error: Prompt must be at least 10 characters long.{ANSI_RESET}"
        )
        sys.exit(1)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Initialize Providers
    providers = [
        OllamaProvider(timeout=DEFAULT_TIMEOUT),
        ClaudeProvider(timeout=DEFAULT_TIMEOUT),
        GeminiProvider(timeout=DEFAULT_TIMEOUT),
        OllamaProvider(
            model="qwen3-coder:30b", timeout=DEFAULT_TIMEOUT
        ),  # Fallback local model
    ]

    orchestrator = Orchestrator(providers)

    # Provider Availability Check
    available_count = sum(1 for p in providers if p.is_available())

    if available_count < 1:
        print(
            f"{ANSI_RED}Error: No available AI providers found. Please install at least one provider (ollama, claude, or gemini).{ANSI_RESET}"
        )
        sys.exit(1)

    # Pre-flight warnings
    missing = [p.name for p in providers if not p.is_available()]
    if missing:
        # Filter out ollama_fallback from missing list (it's shown separately)
        missing_names = [
            p.name if p.name != "ollama" else f"ollama ({p.model})"
            for p in providers
            if not p.is_available()
        ]
        print(
            f"{ANSI_RED}Warning: The following providers are unavailable: {', '.join(missing_names)}. Workflow will use automatic fallback.{ANSI_RESET}"
        )

    # Check if fallback is available
    fallback = orchestrator.get_provider("ollama_fallback")
    if fallback and fallback.is_available():
        print(
            f"{ANSI_GREEN}✓ Fallback local model (qwen3-coder:30b) is available as last resort{ANSI_RESET}"
        )
    else:
        print(
            f"{ANSI_YELLOW}⚠ Fallback local model (qwen3-coder:30b) is not available{ANSI_RESET}"
        )

    # Execute workflow mode
    workflow_timeout = DEFAULT_TIMEOUT * 8  # 8x timeout for 6 steps with buffer
    print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
    print(f"{ANSI_CYAN}ℹ️  Workflow Configuration:{ANSI_RESET}")
    print(
        f"{ANSI_CYAN}   - Per-provider timeout: {DEFAULT_TIMEOUT}s ({DEFAULT_TIMEOUT // 60} minutes){ANSI_RESET}"
    )
    print(
        f"{ANSI_CYAN}   - Total workflow timeout: {workflow_timeout}s ({workflow_timeout // 60} minutes){ANSI_RESET}"
    )
    print(f"{ANSI_CYAN}   - Started at: {time.strftime('%H:%M:%S')}{ANSI_RESET}")
    print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")

    workflow_start = time.time()
    try:
        await asyncio.wait_for(
            mode_workflow(orchestrator, args.prompt, args.output_dir),
            timeout=workflow_timeout,
        )
        workflow_duration = time.time() - workflow_start
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_GREEN}✅ Workflow completed successfully!{ANSI_RESET}")
        print(
            f"{ANSI_GREEN}   Total time: {workflow_duration:.1f}s ({workflow_duration / 60:.1f} minutes){ANSI_RESET}"
        )
        print(f"{ANSI_GREEN}   Finished at: {time.strftime('%H:%M:%S')}{ANSI_RESET}")
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")
    except asyncio.TimeoutError:
        workflow_duration = time.time() - workflow_start
        print(f"\n{ANSI_BOLD}{'=' * 60}{ANSI_RESET}")
        print(f"{ANSI_RED}❌ Error: Workflow timed out!{ANSI_RESET}")
        print(
            f"{ANSI_RED}   Timeout limit: {workflow_timeout}s ({workflow_timeout // 60} minutes){ANSI_RESET}"
        )
        print(
            f"{ANSI_RED}   Time elapsed: {workflow_duration:.1f}s ({workflow_duration / 60:.1f} minutes){ANSI_RESET}"
        )
        print(f"{ANSI_BOLD}{'=' * 60}{ANSI_RESET}\n")
        sys.exit(1)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")


if __name__ == "__main__":
    main()
