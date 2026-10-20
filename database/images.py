"""Storage of the images uploaded to the platform, such as tool logos.

- Read each upload in full with Pillow, so that a file that is not an image is refused.
- Refuse very large images before they are read, and scale down large images.
- Store each image as WebP, without the metadata and the other content of the file.
- Name the file after the SHA-256 of the stored image, so that the content of a file does not change.
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
from linkeddata.profile import settings

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000
LONGEST_SIDE = 2000
FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
NAME = re.compile(r"[0-9a-f]{64}\.webp")


def folder():
    return (database.STATE_DIR / "images").resolve()


def picture_of(stream) -> Picture.Image:
    """Read the image of an uploaded file in full. Raise ValueError if the file is not an image of an accepted
    format."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Picture.DecompressionBombWarning)
            with Picture.open(stream) as opened:
                if opened.format not in FORMATS:
                    raise ValueError("Not a PNG, JPEG, WebP or GIF image.")
                if opened.width * opened.height > MAX_PIXELS:
                    raise ValueError("Over 40 million pixels.")
                opened.load()
                picture = ImageOps.exif_transpose(opened)
    except (UnidentifiedImageError, Picture.DecompressionBombError, Picture.DecompressionBombWarning, OSError) as problem:
        raise ValueError("Not a PNG, JPEG, WebP or GIF image.") from problem
    picture.thumbnail((LONGEST_SIDE, LONGEST_SIDE))
    return picture.convert("RGBA")


def store(stream, name: str, orcid: str) -> str:
    """Store the uploaded image as WebP, with its uploader, and return its address."""
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
