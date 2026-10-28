"""Scan staged git files for accidental secrets. Prints only hit paths, never secret values."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(r"(?m)^MODEL_API_KEY\s*=\s*\S+"),
    re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def main() -> int:
    files = subprocess.check_output(["git", "diff", "--cached", "--name-only"], text=True).splitlines()
    blocked: list[str] = []
    for rel in files:
        path = Path(rel)
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".pyd", ".dll"}:
            continue
        data = path.read_bytes()
        if b"\0" in data[:2048]:
            continue
        text = data.decode("utf-8", "ignore")
        if path.name.endswith(".example"):
            # allow empty MODEL_API_KEY=
            continue
        for pat in PATTERNS:
            m = pat.search(text)
            if not m:
                continue
            # Allow getenv references without literal assignments.
            if "MODEL_API_KEY" in m.group(0) and "os.getenv" in text and not re.search(
                r"(?m)^MODEL_API_KEY\s*=\s*\S+", text
            ):
                continue
            blocked.append(rel)
            break
    print(f"staged_files={len(files)}")
    print(f"secret_hits={len(blocked)}")
    for hit in blocked:
        print(f"HIT {hit}")
    print("env_staged=" + str(any(f.replace("\\", "/") == ".env" for f in files)))
    print("venv_staged=" + str(any(".venv/" in f.replace("\\", "/") or f.startswith(".venv") for f in files)))
    print(
        "node_modules_staged="
        + str(any("node_modules/" in f.replace("\\", "/") for f in files))
    )
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
