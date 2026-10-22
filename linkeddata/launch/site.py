"""Parser of the platform pages in the website templates."""

import json
import re
from urllib.parse import quote

from bs4 import BeautifulSoup, Comment

from linkeddata.profile import settings
from linkeddata.parsers import link, marked, term, slug

PROJECT = "organizations/vhp4safety"
# The licence of the records at launch. It is changed later in the editor, on the platform record.
LICENSE = "https://spdx.org/licenses/CC0-1.0"
SCHEMA = "https://schema.org/"
DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"
# The pages, by the route names of the templates, with the files that are read.
PAGES = {"explore_our_work": "explore_our_work", "impact": "impact", "training": "training",
         "SafetyAssessmentWorkflow": "safety_assessment_workflow", "terms_of_service": "legal/terms_of_service",
         "privacypolicy": "legal/privacypolicy"}
# The headings of the partner list for co-funders, not partners.
FUNDERS = {"Co-funders", "Funder"}


def static(path: str) -> dict:
    """Return a file of the static folder as a link."""
    return link(settings()["base"] + quote(path.strip("/")))


def text(node) -> str:
    """Return the inner HTML of a node without layout."""
    for element in node.find_all(["div", "span"]):
        element.unwrap()
    for element in node.find_all(True):
        element.attrs = {"href": element["href"]} if element.name == "a" and element.get("href") else {}
    for comment in node.find_all(string=lambda found: isinstance(found, Comment)):
        comment.extract()
    return " ".join("".join(str(part) for part in node.contents).split())


def media(node) -> tuple[list, list]:
    """Return the figures and videos of a text, and remove them from it."""
    figures = []
    for image in node.find_all("img"):
        figures.append({"@type": "ImageObject", "contentUrl": static(image["src"]), "caption": image.get("alt", "")})
        (image.find_parent("div", class_="card-img-top") or image).decompose()
    videos = []
    for frame in node.find_all("iframe"):
        videos.append({"@type": "VideoObject", "name": frame.get("title"), "embedUrl": link(frame["src"])})
        holder = frame.find_parent("div")
        (holder if holder is not None and holder is not node else frame).decompose()
    return figures, videos


def item(entry, position: int) -> dict:
    """Return an accordion item as a section."""
    body = entry.select_one(".accordion-body")
    figures, videos = media(body)
    section = {"@type": "WebPageElement", "name": entry.select_one(".accordion-button").get_text(" ", strip=True), "position": position}
    found = text(body)
    if found:
        section["text"] = marked(found)
    if figures:
        section["image"] = figures
    if videos:
        section["video"] = videos
    return section


def tabs(soup) -> list[dict]:
    """Return the tabs of a page as sections, in their order."""
    labels = {}
    for anchor in soup.select("a.nav-link"):
        labels[anchor["href"].lstrip("#")] = (anchor.get_text(" ", strip=True), True)
    for comment in soup.find_all(string=lambda found: isinstance(found, Comment)):
        for anchor in BeautifulSoup(str(comment), "html.parser").select("a.nav-link"):
            labels.setdefault(anchor["href"].lstrip("#"), (anchor.get_text(" ", strip=True), False))
    sections = []
    for pane in soup.select("div.tab-pane"):
        label, shown = labels.get(pane["id"], ("", False))
        section = {"@type": "WebPageElement", "name": label, "position": len(sections) + 1}
        if not shown:
            section["creativeWorkStatus"] = "hidden"
        teaser = pane.find("p", recursive=False)
        if teaser is not None:
            section["text"] = marked(str(BeautifulSoup(f"<p>{text(teaser)}</p>", "html.parser")))
        items = []
        for entry in pane.select("div.accordion-item"):
            items.append(item(entry, len(items) + 1))
        if items:
            section["hasPart"] = items
        sections.append(section)
    return sections


def heading(soup) -> tuple[str, str]:
    """Return the name of a page and the line under it."""
    title = soup.find("h1")
    lead = soup.select_one("p.fs-5")
    return " ".join(title.get_text(" ").split()), " ".join(lead.get_text(" ").split()) if lead is not None else ""


def page(key: str, content: bytes) -> dict:
    """Return the row of a page with its sections."""
    soup = BeautifulSoup(content, "html.parser")
    name, description = heading(soup)
    row = {"@id": PAGES[key], "@type": "WebPage", "name": name}
    if description:
        row["description"] = description
    sections = tabs(soup)
    if not sections:
        body = soup.find("section")
        for found in body.find_all(["h1"]) + body.select("p.fs-5") + body.select(".accordion"):
            found.decompose()
        found = text(body)
        if "process_flow_steps" in str(content):
            row["about"] = term("Process Flow Step", "glossary")
            found = re.sub(r"\{%.*?%\}|\{\{.*?\}\}", "", found).strip()
        if found:
            sections = [{"@type": "WebPageElement", "text": marked(found), "position": 1}]
    if sections:
        row["hasPart"] = sections
    return row


def grant(section: dict) -> tuple[dict, dict] | None:
    """Return the grant and the funder of a funding text, or None."""
    given = section.get("text")
    soup = BeautifulSoup(given["@value"] if isinstance(given, dict) else str(given or ""), "html.parser")
    anchor = soup.find("a")
    if anchor is None:
        return None
    number = anchor.get_text().strip("() ")
    row = {"@id": "grants/" + slug(number), "@type": "MonetaryGrant", "identifier": number, "url": link(anchor["href"]),
           "description": section["text"]}
    words = soup.get_text(" ")
    called = re.search(r"[‘'\"](.+?)[’'\"]", words)
    row["name"] = called.group(1) if called else number
    amount = re.search(r"([\d.]+) million euro grant", words)
    if amount:
        row["amount"] = {"@type": "MonetaryAmount", "value": {"@value": str(round(float(amount.group(1)) * 1000000)), "@type": DECIMAL}, "currency": "EUR"}
    funder = None
    named = re.search(r"funded by the (.+?) through", words)
    if named:
        funder = {"@id": "organizations/" + slug(named.group(1)), "@type": "Organization", "name": named.group(1)}
        row["funder"] = link(funder["@id"])
    return row, funder


def project(about: dict) -> tuple[dict, list[dict]]:
    """Return the row of the project, with its items, and the grant rows."""
    row = {"@id": PROJECT, "@type": "ResearchProject", "name": "VHP4Safety"}
    kept = []
    others = []
    for position, section in enumerate(about.get("hasPart", [])):
        found = section.get("text")
        words = BeautifulSoup(found["@value"] if isinstance(found, dict) else str(found or ""), "html.parser")
        # An item that shows fields of another record keeps its heading and its text.
        shown = {"@type": "WebPageElement", "name": section.get("name"), "position": position + 1}
        if position == 0:
            row["description"] = words.get_text(" ", strip=True)
            # The full name of the project is the heading of the item, before the colon.
            if ":" in section.get("name", ""):
                row["alternateName"] = section["name"].split(":", 1)[0].strip()
            kept.append({**shown, "about": link(PROJECT), "form:shows": [link(SCHEMA + "description")]})
        elif section.get("video"):
            row["subjectOf"] = [link("training/" + slug(video["name"])) for video in section["video"] if video.get("name")]
            if row["subjectOf"]:
                shown.update({"about": row["subjectOf"][0], "form:shows": [link(SCHEMA + "video")]})
            kept.append(shown)
        elif section.get("image") and words.find("ol") is not None:
            row["image"] = section["image"]
            row["subOrganization"] = []
            for entry in words.find_all("li"):
                name, _, what = entry.get_text(" ", strip=True).partition(":")
                row["subOrganization"].append({"@type": "ResearchProject", "name": name.strip(), "description": what.strip()})
            words.find("ol").decompose()
            if words.get_text(strip=True):
                shown["text"] = marked(str(words).strip())
            kept.append({**shown, "about": link(PROJECT), "form:shows": [link(SCHEMA + "subOrganization"), link(SCHEMA + "image")]})
        elif grant(section) is None:
            kept.append({**section, "position": position + 1})
        else:
            given, funder = grant(section)
            row["funding"] = [link(given["@id"])]
            others.append(given)
            if funder is not None:
                others.append(funder)
            kept.append({**shown, "about": link(given["@id"]), "form:shows": [link(SCHEMA + "description")]})
    about["hasPart"] = kept
    return row, others


def partners(content: bytes) -> tuple[list[dict], list[dict], list[dict]]:
    """Return the organisations, the partners and the co-funders of the partner list."""
    organisations = []
    members = []
    funders = []
    role = ""
    for line in content.decode("utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            role = line.lstrip("# ").strip() if "|" not in line and len(line.split()) <= 3 else role
            continue
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        name = parts[1] if len(parts) > 1 and parts[1] else parts[0].rsplit(".", 1)[0]
        row = {"@id": "organizations/" + slug(name), "@type": "Organization", "name": name, "logo": static("static/images/partners/" + parts[0])}
        if len(parts) > 2 and parts[2]:
            row["url"] = link(parts[2])
        organisations.append(row)
        if role in FUNDERS:
            funders.append(link(row["@id"]))
        else:
            members.append(link(row["@id"]))
    return organisations, members, funders


def home(content: bytes, kinds: dict) -> tuple[dict, dict]:
    """Return the catalogue of the platform and its publisher from the home page."""
    soup = BeautifulSoup(content, "html.parser")
    hero = soup.find("h1")
    # The heading keeps its line break ("The Virtual" above "Human Platform").
    lines = [" ".join(line.split()) for line in hero.get_text("\n").split("\n") if line.strip()]
    row = {"@id": "", "@type": "DataCatalog", "alternateName": "\n".join(lines),
           "abstract": " ".join(soup.select_one("p.lead").get_text(" ").split()), "publisher": link(PROJECT), "license": link(LICENSE)}
    row["void:classPartition"] = []
    for card in soup.select("div.card[onclick]"):
        path = re.search(r"location\.href='/(\w+)'", card["onclick"]).group(1)
        row["void:classPartition"].append({"void:class": link(kinds[path]), "name": card.select_one(".card-title").get_text(strip=True),
                                           "description": marked(text(card.select_one(".card-body"))), "position": len(row["void:classPartition"]) + 1})
    about = soup.find(id="main-text-section").find_parent("section")
    row["name"] = " ".join(about.find("h1").get_text(" ").split())
    row["subjectOf"] = []
    for anchor in about.select("a.btn"):
        named = re.search(r"url_for\('(\w+)'\)", anchor["href"])
        if named.group(1) in PAGES:
            row["subjectOf"].append(link(PAGES[named.group(1)]))
    for found in [about.find("h1"), about.find(id="workflowTeaser"), about.select_one("a.btn").find_parent("div", class_="row")] + about.find_all("hr"):
        found.decompose()
    # The line under the heading is the first paragraph of the description. The other large lines are headings of parts.
    for number, found in enumerate(about.select("p.fs-5")):
        if "Safety Assessment Workflow" in found.get_text():
            found.decompose()
        elif number:
            found.name = "h3"
    row["description"] = marked(text(about))
    contact = {"sameAs": []}
    for anchor in soup.select("#contact-section a[href]"):
        if anchor["href"].startswith("mailto:"):
            contact["email"] = anchor["href"].removeprefix("mailto:")
        else:
            contact["sameAs"].append(link(anchor["href"]))
    return row, contact


def organisation(content: bytes) -> dict:
    """Return the organisation in the JSON-LD of a page."""
    soup = BeautifulSoup(content, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        written = script.string or ""
        if '"Organization"' in written and "{{ record_document" not in written:
            return json.loads(written.replace("{{ request.url_root }}", settings()["base"]))
    return {}


def case_studies(content: bytes) -> list[dict]:
    """Return the image of each case study."""
    soup = BeautifulSoup(content, "html.parser")
    found = []
    for card in soup.select("a[href^='/casestudies/']"):
        found.append({"@id": card["href"].strip("/"), "@type": "bioschemas_draft:Study", "image": static(card.find("img")["src"])})
    return found


def parse(contents: dict[str, bytes]) -> list[dict]:
    kinds = settings()["kinds"]
    rows = []
    for key in PAGES:
        rows.append(page(key, contents[key]))
    about = next(row for row in rows if row["@id"] == "explore_our_work")
    about["@type"] = "AboutPage"
    about["mainEntity"] = link(PROJECT)
    found, others = project(about["hasPart"][0])
    # A Publications tab of a page is linked to the grant of the project, so that the outputs of the grant are shown.
    for row in rows:
        for section in row.get("hasPart", []):
            if section.get("name") == "Publications" and found.get("funding") and section.get("creativeWorkStatus") != "hidden":
                section["about"] = found["funding"][0]
    platform, contact = home(contents["home"], kinds)
    found.update({key: value for key, value in contact.items() if value})
    described = organisation(contents["base"])
    for name in [described.get("alternateName")] if described.get("alternateName") else []:
        found.setdefault("alternateName", [])
        found["alternateName"] = ([found["alternateName"]] if isinstance(found["alternateName"], str) else found["alternateName"]) + [name]
    if described.get("logo"):
        found["logo"] = link(described["logo"])
    if described.get("description"):
        found["disambiguatingDescription"] = described["description"]
    for address in described.get("sameAs") or []:
        if link(address) not in found.setdefault("sameAs", []):
            found["sameAs"].append(link(address))
    funder = described.get("funder") or {}
    for row in others:
        if row["@type"] == "Organization" and funder.get("url"):
            row["url"] = link(funder["url"])
    organisations, members, funders = partners(contents["partners"])
    found["member"] = members
    found["funder"] = funders
    return rows + [platform, found] + others + organisations + case_studies(contents["casestudies"])
