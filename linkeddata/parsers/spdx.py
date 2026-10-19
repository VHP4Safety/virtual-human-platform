"""Parser of the SPDX License List (a workaround, see linkeddata/parsers): each licence at
https://spdx.org/licenses/<identifier>, with its name, its identifier as code, and other addresses of its
text (such as at Creative Commons or the Open Source Initiative), so a licence given by any of them is found."""

import json

from linkeddata.parsers import link, present

LICENSES = "https://spdx.org/licenses/"
VOCABULARY = "vocabularies/spdx-license-list"


def parse(content: bytes) -> list[dict]:
    found = json.loads(content)
    rows = [{"@id": VOCABULARY, "@type": "Vocabulary", "name": "SPDX License List", "namespace": LICENSES, "home": link(LICENSES),
             "description": f"The licences of the Software Package Data Exchange, version {found['licenseListVersion']}."}]
    for licence in found["licenses"]:
        row = {"@id": LICENSES + licence["licenseId"], "@type": "Term", "label": licence["name"], "code": licence["licenseId"], "vocabulary": link(VOCABULARY)}
        addresses = []
        for address in licence.get("seeAlso") or []:
            if present(address) and address.startswith(("https://", "http://")):
                addresses.append(link(address.strip()))
        if addresses:
            row["same_as"] = addresses
        rows.append(row)
    return rows
