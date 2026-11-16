"""Export of the platform records to a git repository."""

import os
import re
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import select

import database
from database import images, records
from database.tables import PLATFORM, Record, Revision

RECORDS_DIR = Path(os.environ.get("PLATFORM_RECORDS", "records"))
COMMITTER = ["-c", "user.name=VHP4Safety platform", "-c", "user.email=platform@vhp4safety.nl"]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(RECORDS_DIR), *args], check=True, capture_output=True, text=True)
    return result.stdout


def latest_documents() -> dict[str, str]:
    """Return the latest revision of each platform record that is not removed, by file path."""
    written = select(Record.iri).where(Record.source == PLATFORM, Record.removed_at.is_(None))
    documents = {}
    with database.session() as db:
        for revision in db.scalars(select(Revision).where(Revision.record_iri.in_(written)).order_by(Revision.id)):
            documents[records.path(revision.record_iri) + ".jsonld"] = revision.document
    return documents


def used_images() -> dict[str, Path]:
    """Return the uploaded images that are used anywhere in platform records, by file path."""
    used = {}
    for text in latest_documents().values():
        for name in re.findall(re.escape(records.address("images") + "/") + "(" + images.NAME.pattern + ")", text):
            if (images.folder() / name).exists():
                used["images/" + name] = images.folder() / name
    return used


def export() -> bool:
    """Update the files from the records and commit the change. Return False if nothing changed."""
    if not (RECORDS_DIR / ".git").exists():
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "-b", "main")
    documents = latest_documents()
    pictures = used_images()
    for path in RECORDS_DIR.rglob("*"):
        name = str(path.relative_to(RECORDS_DIR))
        if path.is_file() and ".git" not in path.parts and name not in documents and name not in pictures:
            path.unlink()
    for name, document in documents.items():
        path = RECORDS_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document + "\n", encoding="utf-8")
    for name, source in pictures.items():
        path = RECORDS_DIR / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, path)
    git("add", "--all")
    if not git("status", "--porcelain"):
        return False
    git(*COMMITTER, "commit", "-q", "-m", "Records exported")
    return True


def push() -> None:
    git("push", "-q", "origin", "main")
