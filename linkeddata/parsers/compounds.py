"""Parser of the VHP4Safety compounds: the glossary's table of chemicals, whose identifiers are Compound Wiki's
items, and the fields of those items and of the items that are part of VHP4Safety, as rdfsolve reads them from
Compound Wiki (items). Rows are the compounds, at compound/<item>, with their identifiers and their addresses
in Compound Wiki, Wikidata and the glossary."""

import csv
import io
import json

from linkeddata.parsers import GLOSSARY, link

ITEMS = "https://compoundcloud.wikibase.cloud/entity/"
WIKIDATA = "http://www.wikidata.org/entity/"
# The fields of an item that the model takes, by the name rdfsolve gives each after Compound Wiki's property.
FIELDS = {"label": "name", "alt_label": "alternateName", "short_name": "alternateName", "description": "description", "inchi": "inChI",
          "inchikey": "inChIKey", "smiles": "smiles", "smiles_without_stereochemistry": "smiles", "chemical_formula": "molecularFormula",
          "mass": "molecularWeight"}
# The fields of an item that are identifiers, with the names ROBOT gives their kinds, or else Compound Wiki's.
IDENTIFIERS = {
    "cas_registry_number": "CAS RN",
    "pubchem_cid": "PubChem CID",
    "chebi_id": "ChEBI ID",
    "chembl_id": "ChEMBL ID",
    "dsstox_compound_identifier": "DSSTOX compound identifier",
    "kegg_id": "KEGG ID",
    "hmdb_id": "HMDB ID",
    "ec_number": "EC number",
    "echa_substance_infocard_id": "ECHA Substance Infocard ID",
    "aop_wiki_stressor_id": "AOP-Wiki Stressor ID",
    "cosing_number": "CosIng number",
}


def chemicals(contents: dict[str, bytes]) -> dict[str, dict]:
    """The glossary's chemicals that are Compound Wiki items, by item."""
    found = {}
    for row in csv.DictReader(io.StringIO(contents["chemicals"].decode("utf-8")), delimiter="\t"):
        if row["ID"].startswith("Q"):
            found[row["ID"]] = row
    return found


def items(contents: dict[str, bytes]) -> list[str]:
    return [ITEMS + key for key in sorted(chemicals(contents))]


def parse(contents: dict[str, bytes]) -> list[dict]:
    listed = chemicals(contents)
    rows = []
    for item in json.loads(contents["items"]):
        key = item["item"].removeprefix(ITEMS)
        row = {"@id": f"compound/{key}", "@type": "MolecularEntity", "sameAs": [link(item["item"])], "alternateName": [], "identifier": []}
        for field, name in FIELDS.items():
            row.setdefault(name, []).extend(item.get(field, []))
        for code in item.get("wikidata_q_identifier", []):
            row["sameAs"].append(link(WIKIDATA + code))
        if key in listed:
            row["sameAs"].append(link(GLOSSARY + key))
            if listed[key]["Abbreviation"]:
                row["alternateName"].append(listed[key]["Abbreviation"])
        for field, kind in IDENTIFIERS.items():
            for value in item.get(field, []):
                row["identifier"].append({"@type": "PropertyValue", "propertyID": kind, "value": value})
        rows.append(row)
    return rows
