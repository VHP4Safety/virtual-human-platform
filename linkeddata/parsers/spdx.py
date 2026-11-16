"""Parser of the SPDX License List."""

import json

from linkeddata.parsers import link, present

LICENSES = "https://spdx.org/licenses/"
VOCABULARY = "vocabularies/spdx-license-list"


def parse(content: bytes) -> list[dict]:
    found = json.loads(content)
    rows = [{"@id": VOCABULARY, "@type": "DefinedTermSet", "name": "SPDX License List", "void:uriSpace": LICENSES, "url": link(LICENSES),
             "description": f"The licences of the Software Package Data Exchange, version {found['licenseListVersion']}."}]
    for licence in found["licenses"]:
        row = {"@id": LICENSES + licence["licenseId"], "@type": "DefinedTerm", "name": licence["name"], "termCode": licence["licenseId"], "inDefinedTermSet": link(VOCABULARY)}
        addresses = []
        for address in licence.get("seeAlso") or []:
            if present(address) and address.startswith(("https://", "http://")):
                addresses.append(link(address.strip()))
        if addresses:
            row["sameAs"] = addresses
        rows.append(row)
    return rows
