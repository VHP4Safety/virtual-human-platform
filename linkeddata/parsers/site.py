"""Parser of the platform's own pages as the website's templates had them before they were records (a
workaround, see linkeddata/parsers): the main branch's templates at one commit, and its partner list.
- A page's heading is its name, and the line under it its description. Each tab is a section, with the
  paragraph before its items as its text; each item is a section of its own. A tab whose link is commented
  out is kept as a hidden section. Images and videos in a text are figures and videos of their section.
- The home page gives the platform's catalogue: its name, heading, sentence and description, the cards of its
  kinds of records, the pages it links to, and its publisher's contact links.
- Every page's organisation data (base.html's JSON-LD) adds to the project's record its other names, logo,
  one-line description and addresses elsewhere, and the funder's website.
- The project page's first tab gives the project's record: the first item's text is its description; an
  item's video is its video, a list with a figure its research lines and figure, and a grant link its grant.
- The partner list gives the project's partners by role, its co-funders, and their websites and logos.
- The case studies page gives each case study's image.
- A Publications tab lists the outputs of the project's grant."""

import json
import re
from urllib.parse import quote

from bs4 import BeautifulSoup, Comment

from linkeddata.model import settings
from linkeddata.parsers import link, marked, term, slug

PROJECT = "organizations/vhp4safety"
DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"
# The pages, by the templates' route names, and the files read.
PAGES = {"explore_our_work": "explore_our_work", "training": "training", "impact": "impact",
         "SafetyAssessmentWorkflow": "safety_assessment_workflow", "terms_of_service": "legal/terms_of_service",
         "privacypolicy": "legal/privacypolicy"}
# Partner list headings that name co-funders, not partners.
FUNDERS = {"Co-funders", "Funder"}


def static(path: str) -> dict:
    """A file of the website's static folder, at its address on the platform."""
    return link(settings()["base"] + quote(path.strip("/")))


def text(node) -> str:
    """A node's inner HTML without layout: blocks and spans that only lay out are taken away with their
    attributes (links keep their addresses), and spaces are written once."""
    for element in node.find_all(["div", "span"]):
        element.unwrap()
    for element in node.find_all(True):
        element.attrs = {"href": element["href"]} if element.name == "a" and element.get("href") else {}
    for comment in node.find_all(string=lambda found: isinstance(found, Comment)):
        comment.extract()
    return " ".join("".join(str(part) for part in node.contents).split())


def media(node) -> tuple[list, list]:
    """The figures and videos of a text, taken out of it with their frames."""
    figures = []
    for image in node.find_all("img"):
        figures.append({"@type": "Figure", "image": static(image["src"]), "caption": image.get("alt", "")})
        (image.find_parent("div", class_="card-img-top") or image).decompose()
    videos = []
    for frame in node.find_all("iframe"):
        videos.append({"@type": "Video", "title": frame.get("title"), "player": link(frame["src"])})
        holder = frame.find_parent("div")
        (holder if holder is not None and holder is not node else frame).decompose()
    return figures, videos


def item(entry, position: int) -> dict:
    """An accordion item as a section: its button's text, and its body's text, figures and videos."""
    body = entry.select_one(".accordion-body")
    figures, videos = media(body)
    section = {"@type": "Section", "heading": entry.select_one(".accordion-button").get_text(" ", strip=True), "position": position}
    found = text(body)
    if found:
        section["text"] = marked(found)
    if figures:
        section["figures"] = figures
    if videos:
        section["videos"] = videos
    return section


def tabs(soup) -> list[dict]:
    """A page's tabs as sections, in their order: named by their links, hidden when a link is commented out;
    each with its first paragraph as its text, and its items as its sections."""
    labels = {}
    for anchor in soup.select("a.nav-link"):
        labels[anchor["href"].lstrip("#")] = (anchor.get_text(" ", strip=True), True)
    for comment in soup.find_all(string=lambda found: isinstance(found, Comment)):
        for anchor in BeautifulSoup(str(comment), "html.parser").select("a.nav-link"):
            labels.setdefault(anchor["href"].lstrip("#"), (anchor.get_text(" ", strip=True), False))
    sections = []
    for pane in soup.select("div.tab-pane"):
        label, shown = labels.get(pane["id"], ("", False))
        section = {"@type": "Section", "heading": label, "position": len(sections) + 1}
        if not shown:
            section["status"] = "hidden"
        teaser = pane.find("p", recursive=False)
        if teaser is not None:
            section["text"] = marked(str(BeautifulSoup(f"<p>{text(teaser)}</p>", "html.parser")))
        items = []
        for entry in pane.select("div.accordion-item"):
            items.append(item(entry, len(items) + 1))
        if items:
            section["sections"] = items
        sections.append(section)
    return sections


def heading(soup) -> tuple[str, str]:
    """A page's name and the line under it."""
    title = soup.find("h1")
    lead = soup.select_one("p.fs-5")
    return " ".join(title.get_text(" ").split()), " ".join(lead.get_text(" ").split()) if lead is not None else ""


def page(key: str, content: bytes) -> dict:
    """A page and its sections; a page without tabs has one section, of its text after the heading."""
    soup = BeautifulSoup(content, "html.parser")
    name, description = heading(soup)
    row = {"@id": PAGES[key], "@type": "Page", "name": name}
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
            sections = [{"@type": "Section", "text": marked(found), "position": 1}]
    if sections:
        row["sections"] = sections
    return row


def grant(section: dict) -> tuple[dict, dict] | None:
    """The grant and its funder that a funding text names: its number is the text of its link, and its funder
    and amount are as the text words them; the text is the grant's description."""
    soup = BeautifulSoup(section.get("text", {}).get("@value", "") if isinstance(section.get("text"), dict) else "", "html.parser")
    anchor = soup.find("a")
    if anchor is None:
        return None
    number = anchor.get_text().strip("() ")
    row = {"@id": "grants/" + slug(number), "@type": "Grant", "identifier": number, "url": link(anchor["href"]),
           "description": section["text"]}
    words = soup.get_text(" ")
    called = re.search(r"[‘'\"](.+?)[’'\"]", words)
    row["name"] = called.group(1) if called else number
    amount = re.search(r"([\d.]+) million euro grant", words)
    if amount:
        row["amount"] = {"@type": "Amount", "value": {"@value": str(round(float(amount.group(1)) * 1000000)), "@type": DECIMAL}, "currency": "EUR"}
    funder = None
    named = re.search(r"funded by the (.+?) through", words)
    if named:
        funder = {"@id": "organizations/" + slug(named.group(1)), "@type": "Organization", "name": named.group(1)}
        row["funder"] = link(funder["@id"])
    return row, funder


def project(about: dict) -> tuple[dict, list[dict]]:
    """The project's record from the project page's first tab, whose items it takes, and the grant rows."""
    row = {"@id": PROJECT, "@type": "Project", "name": "VHP4Safety"}
    kept = []
    others = []
    for position, section in enumerate(about.get("sections", [])):
        found = section.get("text")
        words = BeautifulSoup(found["@value"] if isinstance(found, dict) else str(found or ""), "html.parser")
        if position == 0:
            row["description"] = words.get_text(" ", strip=True)
            # The item's heading gives the project's full name before its colon.
            if ":" in section.get("heading", ""):
                row["full_name"] = section["heading"].split(":", 1)[0].strip()
        elif section.get("videos"):
            row["videos"] = section["videos"]
        elif section.get("figures") and words.find("ol") is not None:
            row["figures"] = section["figures"]
            row["lines"] = []
            for entry in words.find_all("li"):
                name, _, what = entry.get_text(" ", strip=True).partition(":")
                row["lines"].append({"@type": "Line", "name": name.strip(), "description": what.strip()})
        elif grant(section) is None:
            kept.append({**section, "position": len(kept) + 1})
        else:
            given, funder = grant(section)
            row["grants"] = [link(given["@id"])]
            others.append(given)
            if funder is not None:
                others.append(funder)
    about["sections"] = kept
    return row, others


def partners(content: bytes) -> tuple[list[dict], list[dict], list[dict]]:
    """The partner list's organisations, the project's partners by the heading over them, and its co-funders;
    commented-out entries are left out."""
    organisations = []
    roles = []
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
            roles.append({"@type": "Partner", "organization": link(row["@id"]), "role": role})
    return organisations, roles, funders


def home(content: bytes, kinds: dict) -> tuple[dict, dict]:
    """The platform's catalogue from the home page, and its publisher's email and other addresses."""
    soup = BeautifulSoup(content, "html.parser")
    hero = soup.find("h1")
    row = {"@id": "", "@type": "Platform", "heading": " ".join(hero.get_text(" ").split()),
           "abstract": " ".join(soup.select_one("p.lead").get_text(" ").split()), "publisher": link(PROJECT)}
    row["kinds"] = []
    for card in soup.select("div.card[onclick]"):
        path = re.search(r"location\.href='/(\w+)'", card["onclick"]).group(1)
        row["kinds"].append({"@type": "Kind", "class": link(kinds[path]), "name": card.select_one(".card-title").get_text(strip=True),
                             "description": marked(text(card.select_one(".card-body"))), "position": len(row["kinds"]) + 1})
    about = soup.find(id="main-text-section").find_parent("section")
    row["name"] = " ".join(about.find("h1").get_text(" ").split())
    row["pages"] = []
    for anchor in about.select("a.btn"):
        named = re.search(r"url_for\('(\w+)'\)", anchor["href"])
        row["pages"].append(link(PAGES[named.group(1)]))
    for found in [about.find("h1"), about.find(id="workflowTeaser"), about.select_one("a.btn").find_parent("div", class_="row")] + about.find_all("hr"):
        found.decompose()
    # The line under the heading is the description's first paragraph; the other large lines head its parts.
    for number, found in enumerate(about.select("p.fs-5")):
        if "Safety Assessment Workflow" in found.get_text():
            found.decompose()
        elif number:
            found.name = "h3"
    row["description"] = marked(text(about))
    contact = {"elsewhere": []}
    for anchor in soup.select("#contact-section a[href]"):
        if anchor["href"].startswith("mailto:"):
            contact["email"] = anchor["href"].removeprefix("mailto:")
        else:
            contact["elsewhere"].append(link(anchor["href"]))
    return row, contact


def organisation(content: bytes) -> dict:
    """The organisation that every page described in its JSON-LD, with the platform's address for the page's."""
    soup = BeautifulSoup(content, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        written = script.string or ""
        if '"Organization"' in written and "{{ record_document" not in written:
            return json.loads(written.replace("{{ request.url_root }}", settings()["base"]))
    return {}


def case_studies(content: bytes) -> list[dict]:
    """Each case study's image, from its card."""
    soup = BeautifulSoup(content, "html.parser")
    found = []
    for card in soup.select("a[href^='/casestudies/']"):
        found.append({"@id": card["href"].strip("/"), "@type": "CaseStudy", "image": static(card.find("img")["src"])})
    return found


def parse(contents: dict[str, bytes]) -> list[dict]:
    kinds = settings()["kinds"]
    rows = []
    for key in PAGES:
        rows.append(page(key, contents[key]))
    about = next(row for row in rows if row["@id"] == "explore_our_work")
    about["@type"] = "AboutPage"
    about["subject"] = link(PROJECT)
    found, others = project(about["sections"][0])
    # A Publications tab of a page lists the outputs of the project's grant.
    for row in rows:
        for section in row.get("sections", []):
            if section.get("heading") == "Publications" and found.get("grants") and section.get("status") != "hidden":
                section["about"] = found["grants"][0]
    platform, contact = home(contents["home"], kinds)
    found.update({key: value for key, value in contact.items() if value})
    described = organisation(contents["base"])
    for name in [described.get("alternateName")] if described.get("alternateName") else []:
        found.setdefault("full_name", [])
        found["full_name"] = ([found["full_name"]] if isinstance(found["full_name"], str) else found["full_name"]) + [name]
    if described.get("logo"):
        found["logo"] = link(described["logo"])
    if described.get("description"):
        found["summary"] = described["description"]
    for address in described.get("sameAs") or []:
        if link(address) not in found.setdefault("elsewhere", []):
            found["elsewhere"].append(link(address))
    funder = described.get("funder") or {}
    for row in others:
        if row["@type"] == "Organization" and funder.get("url"):
            row["url"] = link(funder["url"])
    organisations, roles, funders = partners(contents["partners"])
    found["partners"] = roles
    found["cofunders"] = funders
    return rows + [platform, found] + others + organisations + case_studies(contents["casestudies"])
