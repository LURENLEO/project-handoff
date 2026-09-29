"""Conservative heuristic filtering. Never claims exhaustive secret detection."""
import json
import re
from pathlib import Path, PurePosixPath

# Literal credential shapes: key material, tokens in URLs and headers.
HARD_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|AKIA[A-Z0-9]{16})\b"),
    re.compile(r"(?i)https?://[^\s/@]+:[^\s/@]+@"),
    re.compile(r"(?i)(?:[?&](?:token|key|signature|password)=)[^&\s]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
]
# Assignment-shaped matches are often ordinary code (api_key = config["x"]);
# they flag the file for review instead of blocking its capture.
SOFT_PATTERNS = [
    re.compile(r"(?i)(?:password|passwd|secret|api[_-]?key|access[_-]?token|authorization)\s*[\"']?\s*[:=]\s*[\"']?[^\s,;\"'}]+"),
]

PATTERNS = HARD_PATTERNS + SOFT_PATTERNS


def load_redact_config(store):
    """Optional <store>/redact.json: {"allow_globs": [...], "strict": bool}."""
    config = dict(allow_globs=(), strict=False)
    path = Path(store) / "redact.json" if store else None
    if path and path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeError, OSError):
            return config
        if isinstance(value, dict):
            globs = value.get("allow_globs")
            if isinstance(globs, list):
                config["allow_globs"] = tuple(g for g in globs if isinstance(g, str) and g)
            config["strict"] = value.get("strict") is True
    return config


def allowlisted(path, allow_globs):
    import fnmatch
    return isinstance(path, str) and any(fnmatch.fnmatch(path, g) for g in allow_globs)


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


def literal_secret(data):
    text = data.decode("utf-8", errors="replace")
    return any(p.search(text) for p in HARD_PATTERNS)


def assignment_secret(data):
    text = data.decode("utf-8", errors="replace")
    return any(p.search(text) for p in SOFT_PATTERNS)


def contains_secret(data):
    return literal_secret(data) or assignment_secret(data)


def sensitive_path(path):
    name = PurePosixPath(path).name.lower()
    return (name == ".env" or name.startswith(".env.") or name in
            ("credentials", "credentials.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc") or
            name.endswith((".pem", ".key", ".p12", ".pfx")) or clean_text(path) != path)
