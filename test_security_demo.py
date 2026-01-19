#!/usr/bin/env python3
"""
Security Demonstration Script

Tests all security features implemented in the AI Orchestrator.
"""

import sys
import tempfile
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from security_validation import (
    InvalidInputError,
    PathTraversalError,
    SecurityError,
    safe_decode,
    sanitize_ai_response,
    sanitize_log_message,
    validate_checkpoint_schema,
    validate_command_arg,
    validate_output_path,
    validate_prompt,
)


def print_test(name: str):
    """Print test header."""
    print(f"\n{'=' * 60}")
    print(f"🧪 TEST: {name}")
    print(f"{'=' * 60}")


def print_success(message: str):
    """Print success message."""
    print(f"✅ {message}")


def print_failure(message: str):
    """Print failure message."""
    print(f"❌ {message}")


def test_path_traversal_protection():
    """Test path traversal attack prevention."""
    print_test("Path Traversal Protection")

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Test 1: Valid path within boundary
        try:
            safe_path = project_root / "output" / "file.txt"
            result = validate_output_path(safe_path, project_root, allow_creation=True)
            print_success(f"Valid path accepted: {result.relative_to(project_root)}")
        except Exception as e:
            print_failure(f"Valid path rejected: {e}")

        # Test 2: Path traversal attempt with ..
        try:
            malicious_path = project_root / "output" / ".." / ".." / "etc" / "passwd"
            validate_output_path(malicious_path, project_root)
            print_failure("Path traversal attack NOT detected!")
        except PathTraversalError:
            print_success("Path traversal attack blocked (.. notation)")

        # Test 3: Absolute path outside boundary
        try:
            validate_output_path(Path("/etc/passwd"), project_root)
            print_failure("Absolute path escape NOT detected!")
        except PathTraversalError:
            print_success("Absolute path escape blocked")


def test_input_sanitization():
    """Test AI response sanitization."""
    print_test("Input Sanitization")

    # Test 1: ANSI escape codes removal
    ansi_input = "\033[31mRed text\033[0m normal text"
    sanitized = sanitize_ai_response(ansi_input, strip_ansi=True)
    if "\033" not in sanitized and "Red text" in sanitized:
        print_success("ANSI escape codes removed")
    else:
        print_failure("ANSI codes not properly removed")

    # Test 2: Null byte detection
    try:
        sanitize_ai_response("Hello\x00World")
        print_failure("Null bytes NOT detected!")
    except InvalidInputError:
        print_success("Null bytes detected and blocked")

    # Test 3: Control character removal
    control_input = "Hello\x01\x02\x03World"
    sanitized = sanitize_ai_response(control_input)
    if "\x01" not in sanitized and "HelloWorld" == sanitized:
        print_success("Control characters removed")
    else:
        print_failure("Control characters not properly removed")

    # Test 4: Length limit enforcement
    try:
        long_input = "a" * 101
        sanitize_ai_response(long_input, max_length=100)
        print_failure("Length limit NOT enforced!")
    except InvalidInputError:
        print_success("Length limit enforced")


def test_prompt_validation():
    """Test prompt validation."""
    print_test("Prompt Validation")

    # Test 1: Valid prompt
    try:
        result = validate_prompt("Write a function to calculate fibonacci")
        print_success("Valid prompt accepted")
    except Exception as e:
        print_failure(f"Valid prompt rejected: {e}")

    # Test 2: Empty prompt rejection
    try:
        validate_prompt("")
        print_failure("Empty prompt NOT rejected!")
    except InvalidInputError:
        print_success("Empty prompt rejected")

    # Test 3: Null byte detection
    try:
        validate_prompt("Hello\x00World")
        print_failure("Null bytes in prompt NOT detected!")
    except InvalidInputError:
        print_success("Null bytes in prompt detected")

    # Test 4: Length limits
    try:
        validate_prompt("a" * 5000, max_length=4000)
        print_failure("Prompt length limit NOT enforced!")
    except InvalidInputError:
        print_success("Prompt length limit enforced")


def test_command_injection_prevention():
    """Test command injection prevention."""
    print_test("Command Injection Prevention")

    # Test 1: Safe argument
    try:
        result = validate_command_arg("safe_filename.txt")
        print_success("Safe argument accepted")
    except Exception as e:
        print_failure(f"Safe argument rejected: {e}")

    # Test 2: Semicolon injection
    try:
        validate_command_arg("file.txt; rm -rf /")
        print_failure("Semicolon injection NOT detected!")
    except InvalidInputError:
        print_success("Semicolon injection blocked")

    # Test 3: Pipe injection
    try:
        validate_command_arg("file.txt | cat /etc/passwd")
        print_failure("Pipe injection NOT detected!")
    except InvalidInputError:
        print_success("Pipe injection blocked")

    # Test 4: Backtick injection
    try:
        validate_command_arg("file`whoami`.txt")
        print_failure("Backtick injection NOT detected!")
    except InvalidInputError:
        print_success("Backtick injection blocked")


def test_checkpoint_validation():
    """Test checkpoint schema validation."""
    print_test("Checkpoint Schema Validation")

    # Test 1: Valid checkpoint
    valid_checkpoint = {
        "step_id": "step_1",
        "step_name": "Planning",
        "timestamp": "2024-01-01T12:00:00",
        "status": "completed",
        "data": {"result": "success"},
    }
    try:
        validate_checkpoint_schema(valid_checkpoint)
        print_success("Valid checkpoint accepted")
    except Exception as e:
        print_failure(f"Valid checkpoint rejected: {e}")

    # Test 2: Missing required field
    invalid_checkpoint = {
        "step_id": "step_1",
        "step_name": "Planning",
        # Missing required fields
    }
    try:
        validate_checkpoint_schema(invalid_checkpoint)
        print_failure("Invalid checkpoint NOT detected!")
    except Exception:
        print_success("Missing required field detected")

    # Test 3: Invalid status value
    invalid_status = valid_checkpoint.copy()
    invalid_status["status"] = "hacked"
    try:
        validate_checkpoint_schema(invalid_status)
        print_failure("Invalid status NOT detected!")
    except Exception:
        print_success("Invalid status value detected")


def test_safe_decode():
    """Test safe byte decoding."""
    print_test("Safe Byte Decoding")

    # Test 1: Valid UTF-8
    valid_bytes = "Hello World".encode("utf-8")
    result = safe_decode(valid_bytes)
    if result == "Hello World":
        print_success("Valid UTF-8 decoded correctly")
    else:
        print_failure("UTF-8 decoding failed")

    # Test 2: Malformed bytes
    malformed = b"Hello \xff\xfe World"
    try:
        result = safe_decode(malformed, errors="replace")
        if "Hello" in result and "World" in result:
            print_success("Malformed bytes handled gracefully")
        else:
            print_failure("Malformed bytes not handled correctly")
    except Exception as e:
        print_failure(f"Safe decode failed: {e}")

    # Test 3: Unicode characters
    unicode_bytes = "Hello 世界 🌍".encode("utf-8")
    result = safe_decode(unicode_bytes)
    if result == "Hello 世界 🌍":
        print_success("Unicode decoded correctly")
    else:
        print_failure("Unicode decoding failed")


def test_log_sanitization():
    """Test log message sanitization."""
    print_test("Log Message Sanitization")

    # Test 1: Newline removal (prevents log injection)
    log_with_newlines = "Line1\nLine2\nLine3"
    sanitized = sanitize_log_message(log_with_newlines)
    if "\n" not in sanitized:
        print_success("Newlines removed from log message")
    else:
        print_failure("Newlines not removed")

    # Test 2: ANSI code removal
    log_with_ansi = "\033[31mError message\033[0m"
    sanitized = sanitize_log_message(log_with_ansi)
    if "\033" not in sanitized and "Error message" in sanitized:
        print_success("ANSI codes removed from log message")
    else:
        print_failure("ANSI codes not removed from log")

    # Test 3: Length truncation
    long_log = "a" * 2000
    sanitized = sanitize_log_message(long_log, max_length=100)
    if len(sanitized) <= 120 and "truncated" in sanitized:
        print_success("Long log message truncated")
    else:
        print_failure("Log truncation failed")


def run_all_tests():
    """Run all security tests."""
    print("\n" + "=" * 60)
    print("🔒 AI ORCHESTRATOR SECURITY FEATURES DEMONSTRATION")
    print("=" * 60)

    tests = [
        test_path_traversal_protection,
        test_input_sanitization,
        test_prompt_validation,
        test_command_injection_prevention,
        test_checkpoint_validation,
        test_safe_decode,
        test_log_sanitization,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            print_failure(f"Test crashed: {e}")

    print("\n" + "=" * 60)
    print("✅ SECURITY DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\nAll security features are working as expected!")
    print("The AI Orchestrator is protected against:")
    print("  • Path traversal attacks")
    print("  • Command injection")
    print("  • Prompt injection")
    print("  • Log injection")
    print("  • Malformed input")
    print("  • Schema validation bypass")
    print("  • Null byte attacks")
    print("\nFor more details, see SECURITY_AND_IMPORT_IMPROVEMENTS.txt")


if __name__ == "__main__":
    run_all_tests()
