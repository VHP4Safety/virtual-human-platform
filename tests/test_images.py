"""Uploaded images: read in full, made smaller, and saved again as WebP."""

import io

import pytest
from PIL import Image as Picture

from linkeddata import database, images
from linkeddata.database import Image

BASE = "https://platform.vhp4safety.nl/"


def png(width: int, height: int) -> io.BytesIO:
    output = io.BytesIO()
    Picture.new("RGBA", (width, height), (48, 123, 191, 128)).save(output, format="PNG")
    output.seek(0)
    return output


def test_an_image_is_saved_again_as_webp():
    address = images.store(png(30, 20), "Test Editor", "0000-0002-1825-0097")
    name = address.removeprefix(BASE + "images/")
    with Picture.open(images.folder() / name) as saved:
        assert (saved.format, saved.size) == ("WEBP", (30, 20))
    with database.session() as db:
        assert db.get(Image, name.removesuffix(".webp")).name == "Test Editor"
    assert images.store(png(30, 20), "Test Editor", "0000-0002-1825-0097") == address


def test_a_large_image_is_made_smaller(monkeypatch):
    monkeypatch.setattr(images, "LONGEST_SIDE", 10)
    address = images.store(png(40, 20), "Test Editor", "0000-0002-1825-0097")
    with Picture.open(images.folder() / address.removeprefix(BASE + "images/")) as saved:
        assert saved.size == (10, 5)


def test_files_that_are_not_images_are_refused(monkeypatch):
    for content in [b"just text", b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", png(30, 20).getvalue()[:60]]:
        with pytest.raises(ValueError):
            images.store(io.BytesIO(content), "Test Editor", "0000-0002-1825-0097")
    monkeypatch.setattr(images, "MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="pixels"):
        images.store(png(30, 20), "Test Editor", "0000-0002-1825-0097")
