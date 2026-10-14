"""Parsers: a temporary workaround for upstream files that are not clean linked data.

The upstream files hold several values in one text, codes where addresses are meant, yes/no flags
where links are meant, and placeholders for missing values. Until the sources publish clean linked
data, one parser per file cleans it, and nothing else: how the rows become the model is decided by
the rules of the source (sources/<name>.yaml), not here.

A parser takes the downloaded file and returns rows. Each row keeps the upstream names of its
fields, and has its address ("@id", under the platform's base address when it has no scheme) and
its kind ("@type"). Addresses are written as {"@id": ...}. Placeholders are left out. Values the
parser cannot read are passed on as plain text, so the checks of the build report them.
"""

MISSING = {"", "_No response_", "No response", "NA", "Unknown", "no_url", "[TODO]", "[DRAFT]"}


def present(value) -> bool:
    """False for empty values and for the placeholders that upstream files use for them."""
    return value is not None and str(value).strip() not in MISSING


def link(address: str) -> dict:
    return {"@id": address}


def web_link(value: str):
    """A link for a web address; any other text is passed on as it is."""
    text = str(value).strip()
    if text.startswith(("http://", "https://")):
        return link(text)
    return text
