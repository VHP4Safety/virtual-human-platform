"""Tests of the field checks of each kind, through the records API and the editor."""

import json
import os
import re
import sqlite3
import threading
from collections import Counter
from contextlib import closing
from urllib.parse import quote

import pytest
from rdflib import RDFS, BNode, Graph, URIRef
from rdflib.compare import graph_diff, to_isomorphic

from admin import editor, tokens, writes
from database import records
from linkeddata import documents
from linkeddata.profile import fields, hierarchy, jsonld_name, settings

ORCID = "0000-0002-1825-0097"
XSD = "http://www.w3.org/2001/XMLSchema#"
SAMPLES = {"integer": "7", "decimal": "1.5", "boolean": "true", "date": "2024-01-02", "gYear": "2024"}
MISFITS = ["text", "link", "unlisted", "other class"]
OPERATIONS = (["keep", "set", "add", "empty", "empty parts", "empty required", "one more"]
              + ["misfit " + name for name in MISFITS] + ["warned " + name for name in MISFITS])
SERIALIZED = """async (turtle) => {
    const form = document.querySelector("shacl-form");
    const ready = new Promise((resolve) => form.addEventListener("ready", resolve, { once: true }));
    form.removeAttribute("data-values-url");
    form.setAttribute("data-values", turtle);
    await ready;
    while (form.hasAttribute("loading")) {
        await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return form.serialize("text/turtle");
}"""


def listed(given) -> list:
    return given if isinstance(given, list) else [] if given is None else [given]


def fitting(field: dict, holder: str, taken: list):
    """Return a fitting value that the field does not have yet, or None."""
    if field["values"]:
        for value in field["values"]:
            if value not in taken:
                return {"@id": value} if value.startswith("http") else value
        return None
    if field["part"]:
        part = {"@type": jsonld_name(field["classes"][0])}
        if field["addressed"]:
            part["@id"] = f"{holder}/changed-{writes.slug(field['label'])}"
        for inner in fields(field["classes"][0]):
            value = fitting(inner, part.get("@id", holder), []) if inner["required"] and not inner["fixed"] else None
            if value is not None:
                part[inner["name"]] = value
        return part
    if field["classes"]:
        for record in records.search("", field["classes"], limit=200):
            if record.iri not in taken and record.iri != holder and re.search(field["pattern"], record.iri):
                return {"@id": record.iri}
        return None
    if field["address"]:
        return {"@id": "https://example.org/changed"}
    if field["pattern"]:
        return None
    if field["datatype"] in ("", XSD + "string"):
        return "Changed text"
    sample = SAMPLES.get(field["datatype"].removeprefix(XSD))
    return {"@value": sample, "@type": field["datatype"]} if sample else None


def misfits(field: dict) -> dict:
    """Return values that do not fit a field, by kind of misfit."""
    if field["values"]:
        return {"unlisted": {"@id": "https://example.org/unlisted"}}
    found = {}
    if field["classes"] and not field["part"]:
        for of_class in settings()["kinds"].values():
            fits = False
            for above in hierarchy().transitive_objects(URIRef(of_class), RDFS.subClassOf):
                fits = fits or str(above) in field["classes"]
            other = records.search("", [of_class], parts=False, limit=1)
            if not fits and other:
                found["other class"] = {"@id": other[0].iri}
                break
    if field["classes"] or field["address"] or field["datatype"] not in ("", XSD + "string"):
        found["text"] = "A text where a value of another kind belongs"
    else:
        found["link"] = {"@id": "https://example.org/a-link"}
    return found


def operated(operation: str, field: dict, current: list, holder: str):
    """Return the values of a field after an operation, or None if it is unchanged."""
    taken = documents.values({"field": current}, "field")
    if field["part"] and current and operation in ("set", "empty"):
        return None
    if operation == "set" or (operation in ("add", "one more") and field["single"] == (operation == "one more")):
        value = fitting(field, holder, taken)
        if value is None or (operation == "one more" and not current):
            return None
        return [value] if operation == "set" else current + [value]
    if operation in ("empty", "empty parts", "empty required"):
        wanted = field["required"] == (operation == "empty required") and field["part"] == (operation == "empty parts")
        return [] if current and wanted else None
    if operation.startswith(("misfit ", "warned ")) and field["warning"] == operation.startswith("warned "):
        value = misfits(field).get(operation.split(" ", 1)[1])
        return None if value is None else [value]
    return None


def expectation(operation: str, field: dict) -> str:
    if operation in ("empty", "empty parts") and field["recommended"]:
        return "warning"
    if operation in ("set", "add", "empty", "empty parts"):
        return "accepted"
    return "warning" if field["warning"] else "violation"


def changed(document: dict, of_class: str, operation: str, holder: str, path: list, plan: list) -> dict:
    """Return the document with an operation done on each field, and add the expected checks to plan."""
    new = dict(document)
    for field in fields(of_class):
        if field["fixed"]:
            continue
        current = listed(document.get(field["name"]))
        here = path + [field["name"]]
        if field["part"] and operation != "empty parts":
            parts = []
            for part in current:
                if isinstance(part, dict) and len(part) > 1:
                    part = changed(part, field["classes"][0], operation, part.get("@id", holder), here, plan)
                parts.append(part)
            current = new[field["name"]] = parts
        values = operated(operation, field, current, holder)
        if values is not None:
            new[field["name"]] = values
            plan.append({"field": " > ".join(here), "operation": operation, "expect": expectation(operation, field)})
    return new


def difference(intended: Graph, found: Graph) -> dict:
    """Return the statements lost and added, counted by property and value kind."""
    _, lost, added = graph_diff(to_isomorphic(intended), to_isomorphic(found))
    counted = {"lost": Counter(), "added": Counter()}
    for name, triples in (("lost", lost), ("added", added)):
        for _, predicate, value in triples:
            given = "part" if isinstance(value, BNode) else "link" if isinstance(value, URIRef) else "text"
            counted[name][(jsonld_name(str(predicate)), given, "" if given == "part" else str(value))] += 1
    kept = counted["lost"] & counted["added"]
    answer = {"lost": Counter(), "added": Counter(), "examples": []}
    for name in ("lost", "added"):
        for (field, given, value), count in (counted[name] - kept).items():
            answer[name][f"{field} ({given})"] += count
            if len(answer["examples"]) < 6:
                answer["examples"].append(f"{name} {field} ({given}) {value[:80]}")
    return answer


def answered(plan: list, answer: dict, baseline: dict) -> list:
    """Return the checks in answer that differ from the shapes."""
    found = []
    for item in plan:
        top = item["field"]
        told = "violation" if top in answer["fields"] else "warning" if top in answer["warnings"] else "accepted"
        known = top in baseline["fields"] or top in baseline["warnings"]
        if told != item["expect"] and not (item["expect"] == "accepted" and known):
            found.append(f"{item['operation']}: {item['field']} is {told}, the shapes say {item['expect']}")
    return found


@pytest.fixture
def state(tmp_path):
    given = os.environ.get("FIELDS_STATE")
    if not given:
        pytest.skip("FIELDS_STATE names no platform state to change")
    (tmp_path / "state").mkdir(exist_ok=True)
    with closing(sqlite3.connect(os.path.join(given, "platform.sqlite"))) as source, closing(sqlite3.connect(tmp_path / "state" / "platform.sqlite")) as copy:
        source.backup(copy)
    return tmp_path


def test_fields(state, site):
    secret = tokens.create(ORCID, "Test Editor", list(settings()["kinds"]))
    writing = {"Authorization": "Bearer " + secret}
    report, cases = [], []
    for kind, of_class in settings()["kinds"].items():
        chosen = sorted(editor.listing(kind), key=lambda item: item["filled"])
        chosen = [item for item in chosen if not item["record"].removed_at]
        count = int(os.environ.get("FIELDS_RECORDS", "3"))
        picked = [chosen[round(step * (len(chosen) - 1) / max(count - 1, 1))] for step in range(count)] if chosen else []
        for iri in sorted({item["record"].iri for item in picked}):
            original = documents.document(records.graph([iri]), iri)
            path = "/api/" + quote(iri.removeprefix(settings()["base"]), safe="/:")
            baseline = None
            for operation in OPERATIONS:
                plan = []
                document = changed(original, of_class, operation, iri, [], plan)
                if operation != "keep" and not plan:
                    continue
                intended = documents.statements(writes.document(of_class, iri, document))
                cases.append((kind, iri, operation, intended))
                row = {"kind": kind, "record": iri, "operation": operation, "layer": "api", "changes": len(plan)}
                answer = site.put(path + "?preview=true", json=document, headers=writing)
                if answer.status_code != 200:
                    report.append({**row, "issues": [f"preview answered {answer.status_code}: {answer.get_data(as_text=True)[:300]}"]})
                    continue
                baseline = baseline or answer.json
                row["issues"] = answered(plan, answer.json, baseline)
                if not answer.json["fields"]:
                    saved = site.put(path, json=document, headers=writing)
                    if saved.status_code not in (200, 201):
                        row["issues"].append(f"saving answered {saved.status_code}: {saved.get_data(as_text=True)[:300]}")
                    else:
                        row.update(difference(intended, records.graph([iri])))
                    writes.save(original, of_class, "Test Editor", ORCID)
                report.append(row)
    chrome = os.environ.get("FIELDS_CHROME")
    if chrome:
        report += form_rows(site, secret, chrome, cases)
    written = os.environ.get("FIELDS_REPORT", str(state / "fields-report.json"))
    with open(written, "w") as out:
        json.dump(report, out, indent=1, default=dict)
    failing = [row for row in report if row["issues"] or sum(row.get("lost", {}).values()) or sum(row.get("added", {}).values())]
    assert not failing, f"{len(failing)} of {len(report)} changes lose or add statements, or differ from the shapes: {written}"


def form_rows(site, secret: str, chrome: str, cases: list) -> list:
    """Return the statements that the editor form sends back for each changed record."""
    from playwright.sync_api import sync_playwright
    from werkzeug.serving import make_server

    import app as platform

    server = make_server("127.0.0.1", 0, platform.app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    rows = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=chrome)
        page = browser.new_page()
        page.goto(base + "/login/")
        page.fill("input[name=token]", secret)
        page.click("form:has(input[name=token]) button[type=submit]")
        opened = None
        for kind, iri, operation, intended in cases:
            row = {"kind": kind, "record": iri, "operation": operation, "layer": "form", "issues": []}
            try:
                if opened != iri:
                    page.goto(f"{base}/admin/{kind}/?record={quote(iri)}")
                    page.wait_for_function("document.querySelector('shacl-form') && !document.querySelector('shacl-form').hasAttribute('loading')")
                    opened = iri
                given = page.evaluate(SERIALIZED, intended.serialize(format="turtle"))
                row.update(difference(intended, Graph().parse(data=given, format="turtle")))
            except Exception as problem:
                row["issues"].append(f"the form failed: {str(problem)[:300]}")
                opened = None
            rows.append(row)
        browser.close()
    server.shutdown()
    return rows
