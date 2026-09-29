"""Build the release artifact: deterministic skill ZIP plus SHA256SUMS.

Byte-for-byte reproducible: fixed timestamps, sorted entries, no extra metadata.
"""
import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "project-handoff"
STAMP = (1980, 1, 1, 0, 0, 0)


def version_from_changelog():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## v(\d+\.\d+\.\d+)", text, re.M)
    if not match:
        raise SystemExit("CHANGELOG.md has no version header")
    return match.group(1)


def build(output_dir=None, version=None):
    version = version or version_from_changelog()
    out_dir = Path(output_dir) if output_dir else ROOT
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"project-handoff-{version}.zip"
    entries = sorted(p for p in SKILL.rglob("*") if p.is_file())
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in entries:
            info = zipfile.ZipInfo("project-handoff/" + p.relative_to(SKILL).as_posix(), date_time=STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, p.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = out_dir / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, sums, digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="output directory (default: repository root)")
    parser.add_argument("--version", help="override version from CHANGELOG.md")
    args = parser.parse_args()
    artifact, sums_path, sha = build(args.output, args.version)
    print(artifact)
    print(sums_path)
    print(sha)
