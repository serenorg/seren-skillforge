from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import typer

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".yaml",
    ".yml",
    ".json",
    ".env",
    ".example",
    ".py",
    ".sh",
    ".toml",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "tests",
}

AUTH001_PATTERNS = (
    re.compile(r"export\s+SEREN_API_KEY\s*=", re.IGNORECASE),
    re.compile(r"--api-key\s+[\"']?\$[{]?SEREN_API_KEY[}]?[\"']?", re.IGNORECASE),
    re.compile(r"\b(set|configure)\s+SEREN_API_KEY\b", re.IGNORECASE),
    re.compile(r"\b(create|get|copy|paste).{0,32}SEREN API key\b", re.IGNORECASE),
)

SEREN_KEY_ASSIGNMENT_RE = re.compile(r"\bSEREN_API_KEY\s*=\s*([^\s#]+)")

SAFE_PLACEHOLDER_RE = re.compile(
    r"^(\"?<[^>]+>\"?|\"?secret://[^\"]+\"?|\$\{?[A-Z0-9_]+\}?|\"?\")$"
)


class AuthCheckError(Exception):
    """Raised when auth checks fail."""


@dataclass(frozen=True)
class AuthViolation:
    rule_id: str
    path: str
    line: int
    message: str


@dataclass(frozen=True)
class AuthCheckResult:
    ok: bool
    files_scanned: int
    violations: tuple[AuthViolation, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "ok": self.ok,
                "files_scanned": self.files_scanned,
                "violations": [asdict(violation) for violation in self.violations],
            },
            indent=2,
            sort_keys=True,
        )


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name.endswith(".env.example")


def _iter_text_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if _is_text_file(root) else []

    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if _is_text_file(path):
            files.append(path)
    return files


def _scan_file(path: Path, relative: Path) -> list[AuthViolation]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    suffix = path.suffix.lower()
    auth001_enabled = suffix in {".md", ".txt", ".rst", ".sh", ".yaml", ".yml"}
    auth004_enabled = suffix in {
        ".md",
        ".txt",
        ".rst",
        ".sh",
        ".yaml",
        ".yml",
        ".json",
        ".env",
        ".example",
    } or path.name.endswith(".env.example")
    violations: list[AuthViolation] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if auth001_enabled:
            for pattern in AUTH001_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        AuthViolation(
                            rule_id="AUTH001",
                            path=relative.as_posix(),
                            line=idx,
                            message="Forbidden manual Seren auth setup instruction.",
                        )
                    )
                    break

        if auth004_enabled:
            assignment = SEREN_KEY_ASSIGNMENT_RE.search(line)
            if assignment:
                value = assignment.group(1).strip().strip("'")
                if value and not SAFE_PLACEHOLDER_RE.match(value):
                    violations.append(
                        AuthViolation(
                            rule_id="AUTH004",
                            path=relative.as_posix(),
                            line=idx,
                            message="Potential committed Seren credential-like value.",
                        )
                    )

    return violations


def run(path: Path) -> AuthCheckResult:
    if not path.exists():
        raise AuthCheckError(f"Path does not exist: {path}")

    files = _iter_text_files(path)
    violations: list[AuthViolation] = []
    for file_path in files:
        relative = file_path.relative_to(path) if path.is_dir() else file_path
        violations.extend(_scan_file(file_path, relative))

    return AuthCheckResult(
        ok=not violations,
        files_scanned=len(files),
        violations=tuple(violations),
    )


def command(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="File or directory to scan for auth policy violations.",
    ),
    json_out: Path | None = typer.Option(
        None,
        "--json-out",
        help="Optional path to write machine-readable rule results.",
    ),
) -> None:
    try:
        result = run(path=path)
    except AuthCheckError as exc:
        typer.echo(f"FAIL [auth-check] {exc}")
        raise typer.Exit(code=1) from exc

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(result.to_json(), encoding="utf-8")

    if result.ok:
        typer.echo(f"PASS [auth-check] scanned={result.files_scanned} violations=0")
        return

    typer.echo(
        f"FAIL [auth-check] scanned={result.files_scanned} violations={len(result.violations)}"
    )
    for violation in result.violations:
        typer.echo(
            f"[{violation.rule_id}] {violation.path}:{violation.line}: {violation.message}"
        )
    raise typer.Exit(code=1)
