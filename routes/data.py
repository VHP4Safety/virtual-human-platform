"""Pages about the data. /data-quality shows how complete the records are and what the checks of the
imports found; /sources shows where the records come from and how each source becomes the model."""

from flask import Blueprint, render_template

from database.tables import PLATFORM
from linkeddata import quality

blueprint = Blueprint("dashboards", __name__)


@blueprint.get("/data-quality")
def data_quality():
    return render_template(
        "records/quality.html",
        **quality.report(),
        written=PLATFORM,
        page_title="Data quality — VHP4Safety",
        meta_description="How complete the records of the VHP4Safety platform are, and what the checks of the model found.",
    )


@blueprint.get("/sources")
def sources():
    found, written = quality.sources()
    return render_template(
        "records/sources.html",
        sources=found,
        written=written,
        page_title="Sources — VHP4Safety",
        meta_description="Where the records of the VHP4Safety platform come from, and how each source becomes the platform's model.",
    )
