"""Conservative heuristic filtering. Never claims exhaustive secret detection."""
import re
from pathlib import PurePosixPath

PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"(?i)(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization)\s*[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+"),
    re.compile(r"(?i)https?://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"(?i)(?:[?&](?:token|key|signature|password)=)[^&\s]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
]


def clean_text(value):
    for pattern in PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def clean(value):
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {clean_text(k): clean(v) for k, v in value.items()}
    return value


def contains_secret(data):
    text = data.decode("utf-8", errors="replace")
    return clean_text(text) != text


def sensitive_path(path):
    name = PurePosixPath(path).name.lower()
    return (name == ".env" or name.startswith(".env.") or name in
            ("credentials", "credentials.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc") or
            name.endswith((".pem", ".key", ".p12", ".pfx")) or clean_text(path) != path)
