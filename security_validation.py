#!/usr/bin/env python3
"""
Security Validation Module for AI Orchestrator

Provides security controls for:
- Path traversal prevention
- Input sanitization
- Prompt injection protection
- Checkpoint schema validation
"""

import os
import re
import shlex
import unicodedata
from pathlib import Path
from typing import Any, Dict, Optional


# Security exception hierarchy
class SecurityError(Exception):
    """Base exception for security violations."""

    pass


class PathTraversalError(SecurityError):
    """Raised when path traversal attack detected."""

    pass


class InvalidInputError(SecurityError):
    """Raised when input validation fails."""

    pass


class CheckpointValidationError(SecurityError):
    """Raised when checkpoint data is invalid."""

    pass


# Regex patterns for sanitization
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]")


def validate_output_path(
    path: Path, project_root: Path, allow_creation: bool = True
) -> Path:
    """
    Validate output path to prevent path traversal attacks.

    Args:
        path: Target path to validate
        project_root: Project root directory (trust boundary)
        allow_creation: Whether to create parent directories if missing

    Returns:
        Resolved, validated Path object

    Raises:
        PathTraversalError: If path escapes project boundary or is a symlink
        ValueError: If path is invalid
    """
    if not path:
        raise ValueError("Path cannot be empty")

    if not project_root or not project_root.exists():
        raise ValueError(f"Project root does not exist: {project_root}")

    try:
        # Resolve to absolute path and normalize
        resolved_path = path.resolve()
        resolved_root = project_root.resolve()

        # Check if path is within project boundary
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError:
            # Handle macOS /private/var symlink case - check if both resolve to same location
            try:
                # Try comparing with both paths fully resolved
                if not str(resolved_path).startswith(str(resolved_root)):
                    raise PathTraversalError(
                        f"Path '{path}' escapes project boundary '{project_root}'"
                    )
            except Exception:
                raise PathTraversalError(
                    f"Path '{path}' escapes project boundary '{project_root}'"
                )

        # Check for symlinks at any level in the path (skip checking root ancestors)
        current = resolved_path
        checked_paths = set()
        while (
            current != resolved_root and len(checked_paths) < 100
        ):  # Prevent infinite loops
            if current in checked_paths:
                break
            checked_paths.add(current)

            # Only check symlinks for paths that exist and are below the resolved root
            try:
                if current.exists() and current.is_relative_to(resolved_root):
                    if current.is_symlink() and current != resolved_root:
                        raise PathTraversalError(f"Symlink detected in path: {current}")
            except (OSError, ValueError):
                # Path doesn't exist yet or can't be checked - that's okay for creation
                pass

            current = current.parent
            if current == current.parent:  # Reached filesystem root
                break

        # Create parent directories if allowed and needed
        if allow_creation and not resolved_path.parent.exists():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

        return resolved_path

    except OSError as e:
        raise PathTraversalError(f"Path validation failed: {e}")


def sanitize_ai_response(
    content: str, max_length: int = 100000, strip_ansi: bool = True
) -> str:
    """
    Sanitize AI response content before processing or interpolation.

    Args:
        content: Raw AI response content
        max_length: Maximum allowed content length
        strip_ansi: Whether to remove ANSI escape codes

    Returns:
        Sanitized content string

    Raises:
        InvalidInputError: If content contains dangerous patterns
    """
    if not content:
        return ""

    # Check for null bytes
    if "\0" in content:
        raise InvalidInputError("Content contains null bytes")

    # Remove ANSI escape codes if requested
    if strip_ansi:
        content = ANSI_ESCAPE_PATTERN.sub("", content)

    # Remove other control characters (preserve newlines and tabs)
    content = CONTROL_CHAR_PATTERN.sub("", content)

    # Normalize unicode to prevent equivalent-but-different bypass attacks
    content = unicodedata.normalize("NFC", content)

    # Enforce length limit
    if len(content) > max_length:
        raise InvalidInputError(
            f"Content exceeds maximum length ({len(content)} > {max_length})"
        )

    return content


def validate_prompt(prompt: str, min_length: int = 1, max_length: int = 4000) -> str:
    """
    Validate user prompt input.

    Args:
        prompt: User-provided prompt
        min_length: Minimum prompt length
        max_length: Maximum prompt length

    Returns:
        Validated and normalized prompt

    Raises:
        InvalidInputError: If prompt is invalid
    """
    if not prompt or not isinstance(prompt, str):
        raise InvalidInputError("Prompt must be a non-empty string")

    # Strip whitespace
    prompt = prompt.strip()

    if len(prompt) < min_length:
        raise InvalidInputError(f"Prompt too short (minimum {min_length} characters)")

    if len(prompt) > max_length:
        raise InvalidInputError(f"Prompt too long (maximum {max_length} characters)")

    # Check for null bytes
    if "\0" in prompt:
        raise InvalidInputError("Prompt contains null bytes")

    # Normalize unicode
    prompt = unicodedata.normalize("NFC", prompt)

    return prompt


def validate_checkpoint_schema(data: Dict[str, Any]) -> bool:
    """
    Validate checkpoint data schema to prevent injection attacks.

    Args:
        data: Checkpoint data dictionary

    Returns:
        True if valid

    Raises:
        CheckpointValidationError: If schema is invalid
    """
    required_fields = ["step_id", "step_name", "timestamp", "status", "data"]
    valid_statuses = ["completed", "failed", "in_progress"]

    # Type check first
    if not isinstance(data, dict):
        raise CheckpointValidationError(
            f"Checkpoint must be a dictionary, got {type(data).__name__}"
        )

    # Check required fields
    for field in required_fields:
        if field not in data:
            raise CheckpointValidationError(f"Missing required field: {field}")

    # Validate status value
    if data["status"] not in valid_statuses:
        raise CheckpointValidationError(
            f"Invalid status '{data['status']}'. Must be one of: {valid_statuses}"
        )

    # Validate field types
    if not isinstance(data["step_id"], str):
        raise CheckpointValidationError("step_id must be a string")

    if not isinstance(data["step_name"], str):
        raise CheckpointValidationError("step_name must be a string")

    if not isinstance(data["timestamp"], str):
        raise CheckpointValidationError("timestamp must be a string")

    if not isinstance(data["data"], dict):
        raise CheckpointValidationError("data must be a dictionary")

    # Validate optional fields if present
    if "error" in data and data["error"] is not None:
        if not isinstance(data["error"], str):
            raise CheckpointValidationError("error must be a string or None")

    if "duration" in data:
        if not isinstance(data["duration"], (int, float)):
            raise CheckpointValidationError("duration must be a number")

    return True


def safe_decode(data: bytes, encoding: str = "utf-8", errors: str = "replace") -> str:
    """
    Safely decode bytes to string with error handling.

    Args:
        data: Bytes to decode
        encoding: Target encoding
        errors: Error handling strategy

    Returns:
        Decoded string
    """
    try:
        return data.decode(encoding, errors=errors)
    except Exception:
        # Fallback to latin-1 which never fails
        return data.decode("latin-1", errors="replace")


def validate_command_arg(arg: str) -> str:
    """
    Validate and quote command line argument to prevent injection.

    Args:
        arg: Command argument to validate

    Returns:
        Safely quoted argument

    Raises:
        InvalidInputError: If argument contains dangerous patterns
    """
    if not arg or not isinstance(arg, str):
        raise InvalidInputError("Argument must be a non-empty string")

    # Check for null bytes
    if "\0" in arg:
        raise InvalidInputError("Argument contains null bytes")

    # Check for command injection patterns
    dangerous_patterns = [";", "&&", "||", "|", "`", "$", "(", ")"]
    for pattern in dangerous_patterns:
        if pattern in arg:
            raise InvalidInputError(f"Argument contains dangerous pattern: {pattern}")

    # Use shlex.quote for safe shell escaping
    return shlex.quote(arg)


def sanitize_log_message(message: str, max_length: int = 1000) -> str:
    """
    Sanitize log message to prevent log injection attacks.

    Args:
        message: Log message to sanitize
        max_length: Maximum message length

    Returns:
        Sanitized log message
    """
    if not message:
        return ""

    # Remove control characters and ANSI codes
    message = ANSI_ESCAPE_PATTERN.sub("", message)
    message = CONTROL_CHAR_PATTERN.sub("", message)

    # Replace newlines to prevent log splitting
    message = message.replace("\n", " ").replace("\r", " ")

    # Truncate if too long
    if len(message) > max_length:
        message = message[:max_length] + "... (truncated)"

    return message


def validate_file_operation(
    filepath: Path, operation: str, allowed_extensions: Optional[set] = None
) -> bool:
    """
    Validate file operation safety.

    Args:
        filepath: Path to file
        operation: Operation type ('read', 'write', 'delete')
        allowed_extensions: Set of allowed file extensions (e.g., {'.txt', '.py'})

    Returns:
        True if operation is safe

    Raises:
        SecurityError: If operation is unsafe
    """
    if not filepath:
        raise ValueError("Filepath cannot be empty")

    # Check for symlinks
    if filepath.exists() and filepath.is_symlink():
        raise PathTraversalError(f"Symlink detected: {filepath}")

    # Check file extension if restrictions apply
    if allowed_extensions and filepath.suffix not in allowed_extensions:
        raise SecurityError(
            f"File extension '{filepath.suffix}' not allowed. "
            f"Allowed: {allowed_extensions}"
        )

    # Prevent operations on sensitive files
    sensitive_names = {".env", ".git", ".ssh", "id_rsa", "id_dsa", "known_hosts"}
    if filepath.name in sensitive_names:
        raise SecurityError(f"Operation on sensitive file not allowed: {filepath.name}")

    return True
