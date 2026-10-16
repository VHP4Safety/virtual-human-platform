"""Uploaded images, served under /images/ with headers that let browsers only show them as images."""

from flask import Blueprint, abort, send_from_directory

from database.images import NAME, folder

blueprint = Blueprint("images", __name__)


@blueprint.get("/images/<name>")
def image(name: str):
    if not NAME.fullmatch(name):
        abort(404)
    response = send_from_directory(folder(), name, mimetype="image/webp", max_age=31536000)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    return response
