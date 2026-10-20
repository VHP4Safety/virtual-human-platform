"""Parser of the VHP4Safety compounds."""

import csv
import io
import json

from linkeddata.parsers import GLOSSARY, link

ITEMS = "https://compoundcloud.wikibase.cloud/entity/"
WIKIDATA = "http://www.wikidata.org/entity/"
# The fields of an item that are used in the model, by the names given by rdfsolve after the properties of Compound Wiki.
FIELDS = {"label": "name", "alt_label": "alternateName", "short_name": "alternateName", "description": "description", "inchi": "inChI",
          "inchikey": "inChIKey", "smiles": "smiles", "smiles_without_stereochemistry": "smiles", "chemical_formula": "molecularFormula",
          "mass": "molecularWeight"}
# The fields of an item that are identifiers, with the names of their kinds in ROBOT, or else in Compound Wiki.
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
    """Return the chemicals of the glossary that are Compound Wiki items, by item."""
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
