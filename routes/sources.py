"""The /sources page: where the records come from and how each source becomes the model."""

from flask import Blueprint, render_template

from linkeddata import quality

blueprint = Blueprint("sources", __name__)


@blueprint.get("/sources")
def sources():
    found, written = quality.sources()
    return render_template(
        "records/sources.html",
        sources=found,
        written=written,
        page_title="Sources — VHP4Safety",
        meta_description="Where the VHP4Safety platform's records come from, and how each source becomes its model.",
    )
