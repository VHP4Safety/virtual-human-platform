"""The records written on the platform, exported to a git repository (PLATFORM_RECORDS) so that they
outlive the server: one JSON-LD file per record at the path of its page (tools/aop-builder.jsonld),
as its latest revision wrote it. `python -m linkeddata export` writes and commits them, and
`python -m linkeddata push` sends them to the repository's remote; both are meant to run every night.
"""

import os
import subprocess
from pathlib import Path

from sqlalchemy import select

from linkeddata import database
from linkeddata.database import PLATFORM, Record, Revision
from linkeddata.model import settings

RECORDS_DIR = Path(os.environ.get("PLATFORM_RECORDS", "records"))
COMMITTER = ["-c", "user.name=VHP4Safety platform", "-c", "user.email=platform@vhp4safety.nl"]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(RECORDS_DIR), *args], check=True, capture_output=True, text=True)
    return result.stdout


def latest_documents() -> dict[str, str]:
    """The latest revision of each record written on the platform and not removed, by the path of its file."""
    base = settings()["base"]
    written = select(Record.iri).where(Record.source == PLATFORM, Record.removed_at.is_(None))
    documents = {}
    with database.session() as db:
        for revision in db.scalars(select(Revision).where(Revision.record_iri.in_(written)).order_by(Revision.id)):
            documents[revision.record_iri.removeprefix(base) + ".jsonld"] = revision.document
    return documents


def export() -> bool:
    """The files are made to match the records and the change is committed; False when nothing changed."""
    if not (RECORDS_DIR / ".git").exists():
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "-b", "main")
    documents = latest_documents()
    for path in RECORDS_DIR.rglob("*.jsonld"):
        if ".git" not in path.parts and str(path.relative_to(RECORDS_DIR)) not in documents:
            path.unlink()
    for name, document in documents.items():
        path = RECORDS_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document + "\n", encoding="utf-8")
    git("add", "--all")
    if not git("status", "--porcelain"):
        return False
    git(*COMMITTER, "commit", "-q", "-m", "Records exported")
    return True


def push() -> None:
    git("push", "-q", "origin", "main")
