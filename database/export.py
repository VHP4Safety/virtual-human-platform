"""The platform's records, exported to a git repository (PLATFORM_RECORDS) so they outlive the server:
one JSON-LD file per record at its page's path (tools/aop-builder.jsonld), from its latest revision, and
the images they use (images/<sha256>.webp). They are committed by `python -m linkeddata export` and
pushed by `python -m linkeddata push`, both weekly.
"""

import json
import os
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
    """The latest revision of each platform record not removed, by file path."""
    written = select(Record.iri).where(Record.source == PLATFORM, Record.removed_at.is_(None))
    documents = {}
    with database.session() as db:
        for revision in db.scalars(select(Revision).where(Revision.record_iri.in_(written)).order_by(Revision.id)):
            documents[records.path(revision.record_iri) + ".jsonld"] = revision.document
    return documents


def used_images() -> dict[str, Path]:
    """The uploaded images that platform records use, by file path."""
    used = {}
    for text in latest_documents().values():
        document = json.loads(text)
        for node in document.get("@graph", [document]):
            image = node.get("image")
            for item in image if isinstance(image, list) else [image]:
                address = item.get("@id") if isinstance(item, dict) else item
                if isinstance(address, str) and records.path(address).startswith("images/"):
                    path = images.folder() / records.path(address).removeprefix("images/")
                    if path.exists():
                        used[records.path(address)] = path
    return used


def export() -> bool:
    """The files are made to match the records and the change is committed; False when nothing changed."""
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
