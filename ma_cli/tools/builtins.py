"""
Built-in Tools for MA-CLI.

Core tools for file operations, shell execution, testing, and more.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any


def read_file(path: str, max_size: int = 1024 * 1024) -> str:
    """
    Read contents of a file.

    Args:
        path: Path to the file
        max_size: Maximum file size to read (default 1MB)

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is too large
    """
    file_path = Path(path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Not a file: {path}")

    # Check file size
    file_size = file_path.stat().st_size
    if file_size > max_size:
        raise ValueError(f"File too large: {file_size} bytes (max: {max_size})")

    # Security check - ensure file is within workspace
    workspace = os.environ.get("MA_WORKSPACE", os.getcwd())
    try:
        file_path.relative_to(Path(workspace).resolve())
    except ValueError:
        # File is outside workspace - allow but log warning
        pass

    with open(file_path, encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path: str, content: str, create_dirs: bool = True) -> str:
    """
    Write contents to a file.

    Args:
        path: Path to the file
        content: Content to write
        create_dirs: Create parent directories if they don't exist

    Returns:
        Success message

    Raises:
        PermissionError: If write permission denied
    """
    file_path = Path(path).resolve()

    # Create parent directories if needed
    if create_dirs:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    # Security check - ensure file is within workspace
    workspace = os.environ.get("MA_WORKSPACE", os.getcwd())
    try:
        file_path.relative_to(Path(workspace).resolve())
    except ValueError:
        # File is outside workspace - allow but could add stricter checks
        pass

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully wrote {len(content)} bytes to {path}"


def edit_file(path: str, old_text: str, new_text: str, max_replacements: int = 1) -> str:
    """
    Edit a file by replacing text.

    Args:
        path: Path to the file
        old_text: Text to find and replace
        new_text: Replacement text
        max_replacements: Maximum number of replacements to make

    Returns:
        Success message with number of replacements

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If old_text not found
    """
    content = read_file(path)

    # Count occurrences
    count = content.count(old_text)
    if count == 0:
        raise ValueError(f"Text not found in file: {old_text[:50]}...")

    if count > max_replacements:
        raise ValueError(
            f"Found {count} occurrences, but max_replacements={max_replacements}. "
            "Please be more specific in your search text."
        )

    # Perform replacement
    new_content = content.replace(old_text, new_text, max_replacements)

    # Write back
    write_file(path, new_content)

    return f"Successfully replaced {count} occurrence(s) in {path}"


def shell(command: str, timeout: int = 60, cwd: str | None = None) -> dict[str, Any]:
    """
    Execute a shell command.

    Args:
        command: Command to execute
        timeout: Timeout in seconds
        cwd: Working directory

    Returns:
        Dictionary with stdout, stderr, returncode

    Raises:
        TimeoutError: If command times out
    """
    # Dangerous command check
    dangerous_patterns = [
        r"\brm\s+-rf\s+/\b",
        r"\bmke2fs\b",
        r"\bmkfs\b",
        r"\bdd\s+",
        r">\s*/dev/sd[a-z]",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            raise ValueError(f"Dangerous command blocked: {command}")

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd or os.getcwd(),
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def test(
    paths: list[str] | None = None, framework: str | None = None, timeout: int = 300
) -> dict[str, Any]:
    """
    Run tests.

    Args:
        paths: Test paths to run
        framework: Test framework (pytest, unittest, etc.)
        timeout: Timeout in seconds

    Returns:
        Dictionary with test results
    """
    if paths is None:
        paths = ["."]

    # Detect framework
    if framework is None:
        if os.path.exists("pyproject.toml") or os.path.exists("pytest.ini"):
            framework = "pytest"
        elif any(
            f.endswith("_test.py") or f.startswith("test_")
            for f in os.listdir(".")
            if os.path.isfile(f)
        ):
            framework = "pytest"
        else:
            framework = "pytest"  # Default to pytest

    # Build command
    if framework == "pytest":
        cmd = ["python", "-m", "pytest"] + paths + ["-v", "--tb=short"]
    elif framework == "unittest":
        cmd = ["python", "-m", "unittest", "discover"] + paths
    else:
        cmd = [framework] + paths

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "framework": framework,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Tests timed out after {timeout}s",
            "framework": framework,
        }


def search(
    pattern: str,
    paths: list[str] | None = None,
    file_pattern: str | None = None,
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """
    Search for files or content.

    Args:
        pattern: Search pattern (regex for content, glob for files)
        paths: Paths to search in
        file_pattern: File pattern to filter (e.g., '*.py')
        max_results: Maximum number of results

    Returns:
        List of matches with file, line, content
    """
    if paths is None:
        paths = ["."]

    results = []

    for base_path in paths:
        base = Path(base_path)
        if not base.exists():
            continue

        # Find files
        if file_pattern:
            files = list(base.rglob(file_pattern))
        else:
            files = list(base.rglob("*"))

        files = [f for f in files if f.is_file()]

        # Search content
        try:
            regex = re.compile(pattern, re.IGNORECASE)

            for file in files[:max_results]:
                try:
                    content = read_file(str(file), max_size=100 * 1024)  # 100KB limit per file
                    lines = content.split("\n")

                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            results.append(
                                {
                                    "file": str(file),
                                    "line": i,
                                    "content": line.strip()[:200],
                                }
                            )

                            if len(results) >= max_results:
                                return results

                except (UnicodeDecodeError, ValueError):
                    # Skip binary files or files that are too large
                    continue

        except re.error:
            # Pattern might be a glob, try simple string match
            for file in files[:max_results]:
                if pattern.lower() in str(file).lower():
                    results.append(
                        {
                            "file": str(file),
                            "match_type": "filename",
                        }
                    )

    return results


def git(*args, timeout: int = 60) -> dict[str, Any]:
    """
    Execute git operations.

    Args:
        *args: Git arguments
        timeout: Timeout in seconds

    Returns:
        Dictionary with stdout, stderr, returncode
    """
    cmd = ["git"] + list(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }
