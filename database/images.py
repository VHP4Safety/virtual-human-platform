"""Images uploaded to the platform, such as the logo of a tool.

An upload is read in full by Pillow, so a file that only claims to be an image is refused, and a very
large picture is refused before it is read. The picture is made smaller when it is large and saved
again as WebP, which keeps the picture and leaves out the rest of the file (metadata, anything
hidden in it). The file is named after the SHA-256 of what was saved, so it never changes.
"""

import hashlib
import io
import re
import secrets
import warnings

from PIL import Image as Picture
from PIL import ImageOps, UnidentifiedImageError

import database
from database.tables import Image
from linkeddata.model import settings

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000
LONGEST_SIDE = 2000
FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
NAME = re.compile(r"[0-9a-f]{64}\.webp")


def folder():
    return (database.STATE_DIR / "images").resolve()


def picture_of(stream) -> Picture.Image:
    """The picture of an uploaded file, read in full; ValueError when it is not an image the platform takes."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Picture.DecompressionBombWarning)
            with Picture.open(stream) as opened:
                if opened.format not in FORMATS:
                    raise ValueError("The file is not a PNG, JPEG, WebP or GIF image.")
                if opened.width * opened.height > MAX_PIXELS:
                    raise ValueError("The image has too many pixels; the platform takes up to 40 million.")
                opened.load()
                picture = ImageOps.exif_transpose(opened)
    except (UnidentifiedImageError, Picture.DecompressionBombError, Picture.DecompressionBombWarning, OSError) as problem:
        raise ValueError("The file is not a PNG, JPEG, WebP or GIF image.") from problem
    picture.thumbnail((LONGEST_SIDE, LONGEST_SIDE))
    return picture.convert("RGBA")


def store(stream, name: str, orcid: str) -> str:
    """The address of the uploaded image, saved again as WebP; who uploaded it is kept."""
    picture = picture_of(stream)
    output = io.BytesIO()
    picture.save(output, format="WEBP", quality=88)
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    path = folder() / f"{digest}.webp"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{digest}.{secrets.token_hex(8)}.part")
        temporary.write_bytes(content)
        temporary.replace(path)
    with database.session() as db, db.begin():
        if db.get(Image, digest) is None:
            db.add(Image(sha256=digest, width=picture.width, height=picture.height, size=len(content), name=name, orcid=orcid))
    return settings()["base"] + f"images/{digest}.webp"
