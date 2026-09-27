"""Install a verified skill to a new explicit directory; never replace existing work."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path


def install(target):
    source = Path(__file__).resolve().parents[1]
    target = Path(target).absolute()
    for parent in (target, *target.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise SystemExit("Installation through links/junctions is not supported")
    if target.exists():
        raise SystemExit("Target already exists; inspect it before any update")
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    files = {}
    for path in target.rglob("*"):
        if path.is_file():
            rel = path.relative_to(target).as_posix()
            original = source / rel
            if path.read_bytes() != original.read_bytes():
                raise SystemExit("Installed bytes differ: " + rel)
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps(dict(target=str(target), files_verified=len(files), hashes=files,
                          discovery="Files installed and byte-verified; independent new-session discovery not yet tested")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    install(parser.parse_args().target)
