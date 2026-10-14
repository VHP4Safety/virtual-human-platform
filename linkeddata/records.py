"""The platform's own records: one JSON-LD file per record in a git repository, which is their
source of truth. A record's file is at the path of its page (tools/aop-builder.jsonld), every
change is one commit, and `python -m linkeddata push` sends the repository to its remote."""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RECORDS_DIR = Path(os.environ.get("PLATFORM_RECORDS", "records"))
COMMITTER = ["-c", "user.name=VHP4Safety platform", "-c", "user.email=platform@vhp4safety.nl"]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(RECORDS_DIR), *args], check=True, capture_output=True, text=True)
    return result.stdout


def repository() -> None:
    """The records folder is made a git repository when it is not one yet."""
    if not (RECORDS_DIR / ".git").exists():
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "-b", "main")


def record_path(route: str, identifier: str) -> Path:
    return RECORDS_DIR / route / f"{identifier}.jsonld"


def gone_path(route: str, identifier: str) -> Path:
    return RECORDS_DIR / route / f"{identifier}.gone"


def commit(message: str, name: str, orcid: str) -> None:
    """The changes are committed; a write that changes nothing makes no commit."""
    git("add", "--all")
    if not git("status", "--porcelain"):
        return
    git(*COMMITTER, "commit", "-q", "-m", message, "-m", f"Changed-by: {name} https://orcid.org/{orcid}")


def save(route: str, identifier: str, document: dict, name: str, orcid: str) -> None:
    repository()
    path = record_path(route, identifier)
    action = "Changed" if path.exists() else "Added"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    gone_path(route, identifier).unlink(missing_ok=True)
    commit(f"{action} {route}/{identifier}", name, orcid)


def retire(route: str, identifier: str, name: str, orcid: str) -> None:
    """The record is removed and its address is kept as gone, so it is never given to another record."""
    record_path(route, identifier).unlink()
    gone = {"removed": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    gone_path(route, identifier).write_text(json.dumps(gone) + "\n", encoding="utf-8")
    commit(f"Removed {route}/{identifier}", name, orcid)


def remove(route: str, identifier: str, name: str, orcid: str) -> None:
    """The record is removed with no trace in the current files; the git history still has it."""
    record_path(route, identifier).unlink(missing_ok=True)
    gone_path(route, identifier).unlink(missing_ok=True)
    commit(f"Removed {route}/{identifier} permanently", name, orcid)


def taken(route: str, identifier: str) -> bool:
    return record_path(route, identifier).exists() or gone_path(route, identifier).exists()


def files(suffix: str) -> list[Path]:
    """The record files (".jsonld") or the marks of removed records (".gone"), outside .git."""
    found = []
    if RECORDS_DIR.exists():
        for path in sorted(RECORDS_DIR.rglob("*" + suffix)):
            if ".git" not in path.parts:
                found.append(path)
    return found


def push() -> None:
    git("push", "-q", "origin", "main")
