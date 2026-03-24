"""Shared MCP server utilities for BY agent."""

import json

import asyncio
import base64
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")

MAX_PDB_SIZE = 10 * 1024 * 1024  # 10 MB


def _error(msg: str) -> str:
    """Return a JSON-encoded error payload."""
    return json.dumps({"error": msg})


def _load_env_key(key: str, required: bool = True) -> str | None:
    """Read an environment variable.

    Args:
        key: Environment variable name.
        required: If True, raise an error when the key is missing or empty.

    Returns:
        The value of the environment variable, or None if not required and missing.

    Raises:
        EnvironmentError: If the key is required but missing or empty.
    """
    value = os.environ.get(key)
    if not value:
        if required:
            raise EnvironmentError(
                f"Required environment variable {key!r} is not set. "
                f"Please add it to your .env file."
            )
        return None
    return value


async def async_retry(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    backoff: bool = True,
    **kwargs: Any,
) -> Any:
    """Call an async function with exponential backoff on failure.

    Args:
        fn: Async callable to invoke.
        *args: Positional arguments forwarded to *fn*.
        max_retries: Maximum number of attempts (default 3).
        backoff: Use exponential backoff between retries (default True).
        **kwargs: Keyword arguments forwarded to *fn*.

    Returns:
        The return value of *fn* on success.

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                delay = (2**attempt) if backoff else 1
                await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


def _validate_pdb_path(path: str) -> str:
    """Validate a PDB file path.

    Checks that the file exists and is smaller than 10 MB.

    Args:
        path: Path to a PDB file.

    Returns:
        Absolute path string.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file exceeds the size limit.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"PDB file not found: {p}")
    if p.stat().st_size > MAX_PDB_SIZE:
        raise ValueError(
            f"PDB file exceeds {MAX_PDB_SIZE // (1024 * 1024)} MB limit: {p}"
        )
    return str(p)


def _file_to_base64(path: str) -> str:
    """Read a file and return its contents as a base64-encoded string.

    Args:
        path: Path to the file.

    Returns:
        Base64-encoded string of the file contents.
    """
    resolved = Path(path).resolve()
    data = resolved.read_bytes()
    return base64.b64encode(data).decode("ascii")
