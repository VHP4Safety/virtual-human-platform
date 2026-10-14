"""Parser of the cloud catalogue (a workaround, see linkeddata/parsers). service_index.json lists the
tools, and the detail file of each tool (cloud.vhp4safety.nl/service/<id>.json) describes it. Besides
the tools, the rows are the organisations, people, help pages, videos and licenses that tools link to.
"""

import json
import re
import unicodedata

from linkeddata.parsers import link, present, web_link

# The catalogue marks the regulatory questions of a tool with yes/no flags.
QUESTIONS = {
    "reg_q_1a": "casestudies/kidney/Q1",
    "reg_q_1b": "casestudies/kidney/Q2",
    "reg_q_2a": "casestudies/parkinson/Q1",
    "reg_q_2b": "casestudies/parkinson/Q2",
    "reg_q_3a": "casestudies/thyroid/Q1",
    "reg_q_3b": "casestudies/thyroid/Q2",
}
# The catalogue gives this logo to tools that have none.
PLACEHOLDER_LOGO = "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png"
LOGOS = "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/"
VHP4SAFETY = "organizations/vhp4safety"
# License names as the catalogue writes them, and their SPDX identifiers.
LICENSES = {
    "mit": "MIT",
    "mit license": "MIT",
    "apache-2.0": "Apache-2.0",
    "apache-2.0 license": "Apache-2.0",
    "apache 2.0 license": "Apache-2.0",
    "gpl-3.0": "GPL-3.0-only",
    "gnu general public license v3.0": "GPL-3.0-only",
    "gpl-2.0-only": "GPL-2.0-only",
    "gnu affero general public license v3.0": "AGPL-3.0-only",
    "lgpl 2.1": "LGPL-2.1-only",
    "bsd-3-clause license": "BSD-3-Clause",
    "cc-by-4.0": "CC-BY-4.0",
    "cc-by 4.0 international": "CC-BY-4.0",
    "cc-by nc 4.0": "CC-BY-NC-4.0",
    "cc0": "CC0-1.0",
}
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def slug(text: str) -> str:
    """An identifier made from a name, with accents left out: "Millán" is "millan"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def pairs(entry) -> list[tuple[str, str]]:
    """The titles and addresses of an entry such as {"title": "A;B", "url": "https://a;https://b"}."""
    if not isinstance(entry, dict) or not present(entry.get("url")):
        return []
    addresses = str(entry["url"]).split(";")
    titles = str(entry.get("title") or "").split(";")
    found = []
    for position, address in enumerate(addresses):
        title = titles[position].strip() if position < len(titles) else ""
        if address.strip().startswith(("http://", "https://")):
            found.append((title or address.strip(), address.strip()))
    return found


def license_of(text: str) -> tuple[dict | str, dict | None]:
    """The license of a tool: a link to its SPDX page, or to the page the catalogue links, with the
    row of that license; text the parser cannot read is passed on."""
    written = MARKDOWN_LINK.match(text.strip())
    name = written.group(1) if written else text.strip()
    identifier = LICENSES.get(name.lower())
    if identifier:
        address = f"https://spdx.org/licenses/{identifier}"
        return link(address), {"@id": address, "@type": "License", "name": identifier}
    if written and written.group(2).startswith(("http://", "https://")):
        return link(written.group(2)), {"@id": written.group(2), "@type": "License", "name": name}
    return text, None


def readiness(text: str) -> str:
    """A technology readiness level written as "TRL 4"; other text is passed on."""
    number = re.match(r"^(?:TRL\s*)?(\d)\b", text.strip())
    return f"TRL {number.group(1)}" if number else text


def parse(contents: dict[str, bytes]) -> list[dict]:
    index = json.loads(contents["tools"])
    rows = []
    others = {VHP4SAFETY: {"@id": VHP4SAFETY, "@type": "Organization", "name": "VHP4Safety", "url": link("https://vhp4safety.nl/")}}
    for key, entry in index.items():
        detail = json.loads(contents[key]) if key in contents else {}
        instance = detail.get("instance") if isinstance(detail.get("instance"), dict) else {}
        row = {"@id": "tools/" + entry["id"], "@type": "Tool", "service": entry["service"]}
        if present(entry.get("description")):
            row["description"] = entry["description"]
        if present(detail.get("url") or entry.get("main_url")):
            row["main_url"] = web_link(detail.get("url") or entry["main_url"])
        if present(instance.get("url")) and instance.get("url") != detail.get("url"):
            row["instance_url"] = web_link(instance["url"])
        logo = entry.get("png_file_name")
        if present(logo) and logo != PLACEHOLDER_LOGO:
            row["logo"] = link(LOGOS + logo)
        steps = []
        for stage in (detail.get("stage") or entry.get("stage"), detail.get("substage")):
            if present(stage):
                steps.append(web_link(stage))
        if steps:
            row["stage"] = steps
        questions = []
        for flag, question in QUESTIONS.items():
            if str(entry.get(flag)).lower() == "true":
                questions.append(link(question))
        if questions:
            row["questions"] = questions
        if present(detail.get("doi")):
            doi = str(detail["doi"]).strip().removeprefix("https://doi.org/")
            if doi.startswith("10."):
                row["doi"] = link("https://doi.org/" + doi)
                others.setdefault("https://doi.org/" + doi, {"@id": "https://doi.org/" + doi, "@type": "Publication"})
            else:
                row["doi"] = detail["doi"]
        elsewhere = []
        elixir = detail.get("ELIXIR") if isinstance(detail.get("ELIXIR"), dict) else {}
        other = detail.get("Other") if isinstance(detail.get("Other"), dict) else {}
        if present(elixir.get("biotools")):
            elsewhere.append(link("https://bio.tools/" + str(elixir["biotools"]).strip()))
        if present(elixir.get("fairsharing")):
            value = str(elixir["fairsharing"]).strip()
            elsewhere.append(link(value if value.startswith("http") else "https://doi.org/" + value))
        if present(other.get("wikipedia")):
            elsewhere.append(link("https://en.wikipedia.org/wiki/" + str(other["wikipedia"]).strip()))
        if present(other.get("rsd")):
            elsewhere.append(link("https://research-software-directory.org/software/" + str(other["rsd"]).strip()))
        if elsewhere:
            row["same_as"] = elsewhere
        if present(elixir.get("tess")):
            row["tess"] = elixir["tess"]
        if present(instance.get("version")):
            row["version"] = str(instance["version"])
        notes = detail.get("notes") if isinstance(detail.get("notes"), dict) else {}
        written_license = instance.get("license") or detail.get("license") or notes.get("license")
        if present(written_license):
            row["license"], license_row = license_of(str(written_license))
            if license_row:
                others[license_row["@id"]] = license_row
        sources = []
        for address in (instance.get("source"), detail.get("source")):
            if present(address) and web_link(address) not in sources:
                sources.append(web_link(address))
        if sources:
            row["source"] = sources
        downloads = []
        if present(instance.get("docker")):
            downloads.append(web_link(instance["docker"]))
        access = detail.get("access") if isinstance(detail.get("access"), dict) else {}
        packages = access.get("packages") if isinstance(access.get("packages"), dict) else {}
        for address in packages.values():
            if present(address):
                downloads.append(web_link(address))
        if downloads:
            row["downloads"] = downloads
        if present(instance.get("TRL")):
            row["trl"] = readiness(str(instance["TRL"]))
        if present(detail.get("release_notes")):
            row["release_notes"] = detail["release_notes"]
        help_pages = pairs(detail.get("intro")) + pairs(detail.get("demo"))
        deployment = detail.get("deployment_docs") or instance.get("deployment_docs")
        if present(deployment) and str(deployment).startswith(("http://", "https://")):
            help_pages.append(("Deployment guide", str(deployment)))
        for kind, field, found in (("Page", "help", help_pages),
                                   ("Page", "workflows", pairs(detail.get("workflow")) + pairs(detail.get("workflow2"))),
                                   ("Video", "videos", pairs(detail.get("peertube")))):
            if found:
                row[field] = [link(address) for _, address in found]
                for title, address in found:
                    others.setdefault(address, {"@id": address, "@type": kind, "title": title})
        provider = detail.get("provider") if isinstance(detail.get("provider"), dict) else {}
        providers = []
        if present(provider.get("name")):
            identifier = "organizations/" + slug(provider["name"])
            organization = {"@id": identifier, "@type": "Organization", "name": provider["name"]}
            if present(provider.get("url")):
                organization["url"] = web_link(provider["url"])
            others.setdefault(identifier, organization)
            providers.append(link(identifier))
        # A tool runs on the platform when the catalogue says where on it.
        if present(instance.get("vhp-platform")):
            providers.append(link(VHP4SAFETY))
        if providers:
            row["provider"] = providers
        if str(detail.get("developed-by-VHP")).lower() == "true":
            row["creator"] = link(VHP4SAFETY)
        contacts = []
        if isinstance(provider.get("contact"), dict):
            contacts.append(provider["contact"])
        if isinstance(provider.get("additional_contacts"), list):
            contacts.extend(person for person in provider["additional_contacts"] if isinstance(person, dict))
        maintainers = []
        for person in contacts:
            if not present(person.get("name")):
                continue
            identifier = "people/" + slug(person["name"])
            row_of_person = {"@id": identifier, "@type": "Person", "name": person["name"]}
            if present(person.get("email")):
                row_of_person["email"] = person["email"]
            others.setdefault(identifier, row_of_person)
            maintainers.append(link(identifier))
        if maintainers:
            row["maintainer"] = maintainers
        rows.append(row)
    return rows + list(others.values())
