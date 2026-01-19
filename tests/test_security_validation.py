#!/usr/bin/env python3
"""
Comprehensive unit tests for security_validation module.

Tests cover:
- Path traversal prevention
- Input sanitization
- Prompt validation
- Checkpoint schema validation
- Command injection prevention
- File operation safety
"""

import tempfile
import unicodedata
from pathlib import Path

import pytest

from security_validation import (
    CheckpointValidationError,
    InvalidInputError,
    PathTraversalError,
    SecurityError,
    safe_decode,
    sanitize_ai_response,
    sanitize_log_message,
    validate_checkpoint_schema,
    validate_command_arg,
    validate_file_operation,
    validate_output_path,
    validate_prompt,
)


class TestValidateOutputPath:
    """Test path traversal prevention."""

    def test_valid_path_within_boundary(self, tmp_path):
        """Test that valid paths within project boundary are accepted."""
        output_path = tmp_path / "output"
        result = validate_output_path(output_path, tmp_path, allow_creation=True)
        assert result.is_relative_to(tmp_path)
        assert output_path.parent.exists()

    def test_path_traversal_parent_directory(self, tmp_path):
        """Test that .. notation is detected."""
        malicious_path = tmp_path / "output" / ".." / ".." / "etc" / "passwd"
        with pytest.raises(PathTraversalError, match="escapes project boundary"):
            validate_output_path(malicious_path, tmp_path)

    def test_path_traversal_absolute_path(self, tmp_path):
        """Test that absolute paths outside boundary are rejected."""
        with pytest.raises(PathTraversalError, match="escapes project boundary"):
            validate_output_path(Path("/etc/passwd"), tmp_path)

    def test_symlink_detection(self, tmp_path):
        """Test that symlinks are detected and rejected."""
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)

        with pytest.raises(PathTraversalError, match="Symlink detected"):
            validate_output_path(link / "file.txt", tmp_path)

    def test_empty_path(self, tmp_path):
        """Test that empty paths are rejected."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_output_path(Path(""), tmp_path)

    def test_nonexistent_project_root(self, tmp_path):
        """Test that nonexistent project root is rejected."""
        fake_root = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            validate_output_path(tmp_path / "output", fake_root)

    def test_path_normalization(self, tmp_path):
        """Test that paths are properly normalized."""
        output_path = tmp_path / "output" / "." / "subdir"
        result = validate_output_path(output_path, tmp_path, allow_creation=True)
        assert ".." not in str(result)
        assert result.is_relative_to(tmp_path)

    def test_no_creation_flag(self, tmp_path):
        """Test that allow_creation=False doesn't create directories."""
        output_path = tmp_path / "new_dir" / "file.txt"
        result = validate_output_path(output_path, tmp_path, allow_creation=False)
        assert not output_path.parent.exists()
        assert result.is_relative_to(tmp_path)


class TestSanitizeAIResponse:
    """Test AI response sanitization."""

    def test_clean_content(self):
        """Test that clean content passes through."""
        content = "This is clean content."
        result = sanitize_ai_response(content)
        assert result == content

    def test_empty_string(self):
        """Test that empty strings are handled."""
        assert sanitize_ai_response("") == ""

    def test_ansi_escape_removal(self):
        """Test ANSI escape codes are removed."""
        content = "\033[31mRed text\033[0m normal"
        result = sanitize_ai_response(content, strip_ansi=True)
        assert "\033" not in result
        assert "Red text" in result

    def test_null_byte_detection(self):
        """Test that null bytes are detected."""
        content = "Hello\x00World"
        with pytest.raises(InvalidInputError, match="null bytes"):
            sanitize_ai_response(content)

    def test_control_character_removal(self):
        """Test that control characters are removed."""
        content = "Hello\x01\x02\x03World"
        result = sanitize_ai_response(content)
        assert "\x01" not in result
        assert "HelloWorld" == result

    def test_newline_preservation(self):
        """Test that newlines and tabs are preserved."""
        content = "Line1\nLine2\tTabbed"
        result = sanitize_ai_response(content)
        assert "\n" in result
        assert "\t" in result

    def test_unicode_normalization(self):
        """Test that unicode is normalized to NFC."""
        # Decomposed form (NFD) vs composed (NFC)
        nfd_content = "café"  # e + combining accent
        result = sanitize_ai_response(nfd_content)
        assert result == unicodedata.normalize("NFC", nfd_content)

    def test_length_limit_enforcement(self):
        """Test that content exceeding max_length is rejected."""
        content = "a" * 101
        with pytest.raises(InvalidInputError, match="exceeds maximum length"):
            sanitize_ai_response(content, max_length=100)

    def test_complex_ansi_sequences(self):
        """Test removal of complex ANSI sequences."""
        content = "\033[1;32;40mBold Green on Black\033[0m"
        result = sanitize_ai_response(content, strip_ansi=True)
        assert "\033" not in result
        assert "Bold Green on Black" in result

    def test_ansi_preservation_flag(self):
        """Test that ANSI codes can be preserved when requested."""
        content = "\033[31mRed\033[0m"
        result = sanitize_ai_response(content, strip_ansi=False)
        assert "\033" in result


class TestValidatePrompt:
    """Test prompt validation."""

    def test_valid_prompt(self):
        """Test that valid prompts are accepted."""
        prompt = "Write a function to calculate fibonacci"
        result = validate_prompt(prompt)
        assert result == prompt

    def test_empty_prompt(self):
        """Test that empty prompts are rejected."""
        with pytest.raises(InvalidInputError, match="non-empty string"):
            validate_prompt("")

    def test_none_prompt(self):
        """Test that None prompts are rejected."""
        with pytest.raises(InvalidInputError, match="non-empty string"):
            validate_prompt(None)

    def test_whitespace_only_prompt(self):
        """Test that whitespace-only prompts are rejected."""
        with pytest.raises(InvalidInputError, match="too short"):
            validate_prompt("   \n\t  ")

    def test_prompt_too_short(self):
        """Test that prompts below minimum length are rejected."""
        with pytest.raises(InvalidInputError, match="too short"):
            validate_prompt("a", min_length=5)

    def test_prompt_too_long(self):
        """Test that prompts exceeding maximum length are rejected."""
        long_prompt = "a" * 5000
        with pytest.raises(InvalidInputError, match="too long"):
            validate_prompt(long_prompt, max_length=4000)

    def test_null_byte_rejection(self):
        """Test that prompts with null bytes are rejected."""
        with pytest.raises(InvalidInputError, match="null bytes"):
            validate_prompt("Hello\x00World")

    def test_unicode_normalization_in_prompt(self):
        """Test that prompts are normalized."""
        prompt = "café"  # May be in NFD form
        result = validate_prompt(prompt)
        assert result == unicodedata.normalize("NFC", prompt)

    def test_whitespace_stripping(self):
        """Test that leading/trailing whitespace is stripped."""
        prompt = "  Hello World  "
        result = validate_prompt(prompt)
        assert result == "Hello World"

    def test_non_string_prompt(self):
        """Test that non-string prompts are rejected."""
        with pytest.raises(InvalidInputError, match="non-empty string"):
            validate_prompt(123)

    def test_boundary_min_length(self):
        """Test prompt at exact minimum length."""
        prompt = "Hello"
        result = validate_prompt(prompt, min_length=5)
        assert result == prompt

    def test_boundary_max_length(self):
        """Test prompt at exact maximum length."""
        prompt = "a" * 100
        result = validate_prompt(prompt, max_length=100)
        assert result == prompt


class TestValidateCheckpointSchema:
    """Test checkpoint schema validation."""

    def test_valid_checkpoint(self):
        """Test that valid checkpoint data is accepted."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {"result": "success"},
        }
        assert validate_checkpoint_schema(data) is True

    def test_missing_required_field(self):
        """Test that missing required fields are detected."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            # Missing timestamp, status, data
        }
        with pytest.raises(CheckpointValidationError, match="Missing required field"):
            validate_checkpoint_schema(data)

    def test_invalid_status_value(self):
        """Test that invalid status values are rejected."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "invalid_status",
            "data": {},
        }
        with pytest.raises(CheckpointValidationError, match="Invalid status"):
            validate_checkpoint_schema(data)

    def test_all_valid_statuses(self):
        """Test all valid status values."""
        valid_statuses = ["completed", "failed", "in_progress"]
        for status in valid_statuses:
            data = {
                "step_id": "step_1",
                "step_name": "Test",
                "timestamp": "2024-01-01T12:00:00",
                "status": status,
                "data": {},
            }
            assert validate_checkpoint_schema(data) is True

    def test_invalid_step_id_type(self):
        """Test that non-string step_id is rejected."""
        data = {
            "step_id": 123,  # Should be string
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {},
        }
        with pytest.raises(CheckpointValidationError, match="step_id must be a string"):
            validate_checkpoint_schema(data)

    def test_invalid_data_type(self):
        """Test that non-dict data is rejected."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": "not a dict",
        }
        with pytest.raises(
            CheckpointValidationError, match="data must be a dictionary"
        ):
            validate_checkpoint_schema(data)

    def test_optional_error_field(self):
        """Test that optional error field is validated."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "failed",
            "data": {},
            "error": "Something went wrong",
        }
        assert validate_checkpoint_schema(data) is True

    def test_invalid_error_type(self):
        """Test that non-string error is rejected."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "failed",
            "data": {},
            "error": 123,  # Should be string or None
        }
        with pytest.raises(CheckpointValidationError, match="error must be a string"):
            validate_checkpoint_schema(data)

    def test_valid_duration_field(self):
        """Test that valid duration field is accepted."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {},
            "duration": 12.5,
        }
        assert validate_checkpoint_schema(data) is True

    def test_invalid_duration_type(self):
        """Test that non-numeric duration is rejected."""
        data = {
            "step_id": "step_1",
            "step_name": "Planning",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {},
            "duration": "12 seconds",
        }
        with pytest.raises(
            CheckpointValidationError, match="duration must be a number"
        ):
            validate_checkpoint_schema(data)

    def test_non_dict_checkpoint(self):
        """Test that non-dict checkpoint is rejected."""
        with pytest.raises(CheckpointValidationError, match="must be a dictionary"):
            validate_checkpoint_schema("not a dict")


class TestSafeDecode:
    """Test safe byte decoding."""

    def test_valid_utf8(self):
        """Test decoding valid UTF-8 bytes."""
        data = "Hello World".encode("utf-8")
        result = safe_decode(data)
        assert result == "Hello World"

    def test_malformed_bytes(self):
        """Test handling of malformed bytes."""
        data = b"Hello \xff World"
        result = safe_decode(data, errors="replace")
        assert "Hello" in result
        assert "World" in result

    def test_empty_bytes(self):
        """Test decoding empty bytes."""
        result = safe_decode(b"")
        assert result == ""

    def test_unicode_characters(self):
        """Test decoding unicode characters."""
        data = "Hello 世界 🌍".encode("utf-8")
        result = safe_decode(data)
        assert result == "Hello 世界 🌍"

    def test_custom_encoding(self):
        """Test decoding with custom encoding."""
        data = "Hello".encode("latin-1")
        result = safe_decode(data, encoding="latin-1")
        assert result == "Hello"

    def test_mixed_valid_invalid(self):
        """Test decoding mixed valid/invalid bytes."""
        data = b"Valid\xffInvalid\xfe"
        result = safe_decode(data, errors="replace")
        assert "Valid" in result
        assert "Invalid" in result


class TestValidateCommandArg:
    """Test command argument validation."""

    def test_valid_simple_arg(self):
        """Test that simple arguments are accepted."""
        result = validate_command_arg("hello")
        assert "hello" in result

    def test_semicolon_injection(self):
        """Test that semicolons are detected."""
        with pytest.raises(InvalidInputError, match="dangerous pattern"):
            validate_command_arg("hello; rm -rf /")

    def test_pipe_injection(self):
        """Test that pipes are detected."""
        with pytest.raises(InvalidInputError, match="dangerous pattern"):
            validate_command_arg("hello | cat /etc/passwd")

    def test_backtick_injection(self):
        """Test that backticks are detected."""
        with pytest.raises(InvalidInputError, match="dangerous pattern"):
            validate_command_arg("hello`whoami`")

    def test_dollar_expansion(self):
        """Test that dollar signs are detected."""
        with pytest.raises(InvalidInputError, match="dangerous pattern"):
            validate_command_arg("hello$USER")

    def test_null_byte_in_arg(self):
        """Test that null bytes are detected."""
        with pytest.raises(InvalidInputError, match="null bytes"):
            validate_command_arg("hello\x00world")

    def test_empty_arg(self):
        """Test that empty arguments are rejected."""
        with pytest.raises(InvalidInputError, match="non-empty string"):
            validate_command_arg("")

    def test_shlex_quoting(self):
        """Test that arguments are properly quoted."""
        result = validate_command_arg("file name with spaces.txt")
        # shlex.quote should add quotes
        assert "'" in result or '"' in result or "\\" in result


class TestSanitizeLogMessage:
    """Test log message sanitization."""

    def test_clean_message(self):
        """Test that clean messages pass through."""
        message = "Operation completed successfully"
        result = sanitize_log_message(message)
        assert result == message

    def test_newline_replacement(self):
        """Test that newlines are replaced to prevent log injection."""
        message = "Line1\nLine2\nLine3"
        result = sanitize_log_message(message)
        assert "\n" not in result
        assert "Line1 Line2 Line3" == result

    def test_ansi_removal_in_logs(self):
        """Test that ANSI codes are removed from logs."""
        message = "\033[31mError message\033[0m"
        result = sanitize_log_message(message)
        assert "\033" not in result
        assert "Error message" in result

    def test_length_truncation(self):
        """Test that long messages are truncated."""
        message = "a" * 2000
        result = sanitize_log_message(message, max_length=100)
        assert len(result) <= 120  # 100 + "... (truncated)"
        assert "truncated" in result

    def test_empty_message(self):
        """Test that empty messages are handled."""
        assert sanitize_log_message("") == ""


class TestValidateFileOperation:
    """Test file operation safety validation."""

    def test_valid_operation(self, tmp_path):
        """Test that valid operations are accepted."""
        filepath = tmp_path / "test.txt"
        assert validate_file_operation(filepath, "read") is True

    def test_symlink_rejection(self, tmp_path):
        """Test that symlinks are rejected."""
        target = tmp_path / "target.txt"
        target.write_text("content")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        with pytest.raises(PathTraversalError, match="Symlink detected"):
            validate_file_operation(link, "read")

    def test_extension_restriction(self, tmp_path):
        """Test that file extension restrictions work."""
        filepath = tmp_path / "script.exe"
        with pytest.raises(SecurityError, match="not allowed"):
            validate_file_operation(
                filepath, "write", allowed_extensions={".txt", ".py"}
            )

    def test_allowed_extension(self, tmp_path):
        """Test that allowed extensions pass validation."""
        filepath = tmp_path / "script.py"
        assert (
            validate_file_operation(
                filepath, "write", allowed_extensions={".txt", ".py"}
            )
            is True
        )

    def test_sensitive_file_rejection(self, tmp_path):
        """Test that sensitive files are rejected."""
        sensitive_files = [".env", ".git", ".ssh", "id_rsa"]
        for filename in sensitive_files:
            filepath = tmp_path / filename
            with pytest.raises(SecurityError, match="sensitive file"):
                validate_file_operation(filepath, "read")

    def test_empty_filepath(self):
        """Test that empty filepaths are rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_file_operation(None, "read")


class TestSecurityErrorHierarchy:
    """Test exception hierarchy."""

    def test_path_traversal_is_security_error(self):
        """Test that PathTraversalError inherits from SecurityError."""
        assert issubclass(PathTraversalError, SecurityError)

    def test_invalid_input_is_security_error(self):
        """Test that InvalidInputError inherits from SecurityError."""
        assert issubclass(InvalidInputError, SecurityError)

    def test_checkpoint_validation_is_security_error(self):
        """Test that CheckpointValidationError inherits from SecurityError."""
        assert issubclass(CheckpointValidationError, SecurityError)

    def test_security_error_is_exception(self):
        """Test that SecurityError inherits from Exception."""
        assert issubclass(SecurityError, Exception)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exact_min_length_prompt(self):
        """Test prompt at exact minimum length boundary."""
        prompt = "a" * 10
        result = validate_prompt(prompt, min_length=10)
        assert result == prompt

    def test_exact_max_length_prompt(self):
        """Test prompt at exact maximum length boundary."""
        prompt = "a" * 100
        result = validate_prompt(prompt, max_length=100)
        assert result == prompt

    def test_root_directory_as_output(self, tmp_path):
        """Test using root directory itself as output."""
        result = validate_output_path(tmp_path, tmp_path)
        assert result == tmp_path.resolve()

    def test_checkpoint_with_empty_data(self):
        """Test checkpoint with empty but valid data dict."""
        data = {
            "step_id": "step_1",
            "step_name": "Test",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {},  # Empty but valid
        }
        assert validate_checkpoint_schema(data) is True

    def test_checkpoint_with_nested_data(self):
        """Test checkpoint with complex nested data."""
        data = {
            "step_id": "step_1",
            "step_name": "Test",
            "timestamp": "2024-01-01T12:00:00",
            "status": "completed",
            "data": {
                "level1": {"level2": {"level3": ["value1", "value2"]}},
                "array": [1, 2, 3],
            },
        }
        assert validate_checkpoint_schema(data) is True
