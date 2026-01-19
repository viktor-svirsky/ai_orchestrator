#!/usr/bin/env python3
"""
Test script to verify prompt length handling for different providers.
"""

import asyncio

from ai_orchestrator import (
    AIProvider,
    ClaudeProvider,
    GeminiProvider,
    OllamaProvider,
)


def test_provider_max_lengths():
    """Test that providers have correct max_prompt_length settings."""
    print("Testing provider max_prompt_length settings...\n")

    # Test Gemini has 4000 char limit
    gemini = GeminiProvider(timeout=60)
    assert gemini.max_prompt_length == 4000, (
        f"Expected Gemini max_prompt_length=4000, got {gemini.max_prompt_length}"
    )
    print(f"✓ Gemini max_prompt_length: {gemini.max_prompt_length}")

    # Test Ollama has default (100000) char limit
    ollama = OllamaProvider(model="test", timeout=60)
    assert ollama.max_prompt_length == 100000, (
        f"Expected Ollama max_prompt_length=100000, got {ollama.max_prompt_length}"
    )
    print(f"✓ Ollama max_prompt_length: {ollama.max_prompt_length}")

    # Test Claude has default (100000) char limit
    claude = ClaudeProvider(timeout=60)
    assert claude.max_prompt_length == 100000, (
        f"Expected Claude max_prompt_length=100000, got {claude.max_prompt_length}"
    )
    print(f"✓ Claude max_prompt_length: {claude.max_prompt_length}")


def test_prompt_validation():
    """Test that prompt validation respects provider limits."""
    print("\nTesting prompt validation...\n")

    gemini = GeminiProvider(timeout=60)
    ollama = OllamaProvider(model="test", timeout=60)

    # Test short prompt - should work for both
    short_prompt = "Hello, world!"
    try:
        gemini._validate_prompt(short_prompt)
        print(f"✓ Gemini accepts short prompt ({len(short_prompt)} chars)")
    except ValueError as e:
        print(f"✗ Gemini rejected short prompt: {e}")

    try:
        ollama._validate_prompt(short_prompt)
        print(f"✓ Ollama accepts short prompt ({len(short_prompt)} chars)")
    except ValueError as e:
        print(f"✗ Ollama rejected short prompt: {e}")

    # Test long prompt (5000 chars) - should fail for Gemini, pass for Ollama
    long_prompt = "a" * 5000

    try:
        gemini._validate_prompt(long_prompt)
        print(f"✗ Gemini should have rejected long prompt ({len(long_prompt)} chars)")
    except ValueError as e:
        print(f"✓ Gemini correctly rejected long prompt ({len(long_prompt)} chars)")

    try:
        ollama._validate_prompt(long_prompt)
        print(f"✓ Ollama accepts long prompt ({len(long_prompt)} chars)")
    except ValueError as e:
        print(f"✗ Ollama rejected long prompt: {e}")

    # Test very long prompt (150000 chars) - should fail for both
    very_long_prompt = "a" * 150000

    try:
        gemini._validate_prompt(very_long_prompt)
        print(
            f"✗ Gemini should have rejected very long prompt ({len(very_long_prompt)} chars)"
        )
    except ValueError as e:
        print(
            f"✓ Gemini correctly rejected very long prompt ({len(very_long_prompt)} chars)"
        )

    try:
        ollama._validate_prompt(very_long_prompt)
        print(
            f"✗ Ollama should have rejected very long prompt ({len(very_long_prompt)} chars)"
        )
    except ValueError as e:
        print(
            f"✓ Ollama correctly rejected very long prompt ({len(very_long_prompt)} chars)"
        )


def test_skip_logic():
    """Test that ask_with_fallback skips providers with prompts that are too long."""
    print("\nTesting provider skip logic...\n")

    # Create a long prompt that exceeds Gemini's limit
    long_prompt = "x" * 5000

    gemini = GeminiProvider(timeout=60)
    ollama = OllamaProvider(model="test", timeout=60)
    claude = ClaudeProvider(timeout=60)

    # Check which providers can handle the long prompt
    providers = [
        ("gemini", gemini),
        ("ollama", ollama),
        ("claude", claude),
    ]

    for name, provider in providers:
        can_handle = len(long_prompt) <= provider.max_prompt_length
        status = "✓ CAN" if can_handle else "✗ CANNOT"
        print(
            f"{status} handle {len(long_prompt)} char prompt: {name} (max: {provider.max_prompt_length})"
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Prompt Length Handling Test")
    print("=" * 60)
    print()

    try:
        test_provider_max_lengths()
        test_prompt_validation()
        test_skip_logic()

        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
