"""Parser of the cloud catalogue (a workaround, see linkeddata/parsers). service_index.json lists the
tools, and the detail file of each tool (cloud.vhp4safety.nl/service/<id>.json) describes it. Besides
the tools, the rows are the organisations, people and publications that tools link to; the help pages
and videos of a tool are parts of its row.
"""

import json
import re

from linkeddata.parsers import QUESTIONS, link, present, publication, slug, term, web_link

# The catalogue gives this logo to tools that have none.
PLACEHOLDER_LOGO = "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png"
LOGOS = "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/"
VHP4SAFETY = "organizations/vhp4safety"


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
        # The catalogue's stage is a process flow step, and its substage a term of what the tool deals with.
        if present(detail.get("stage") or entry.get("stage")):
            row["step"] = web_link(detail.get("stage") or entry["stage"])
        if present(detail.get("substage")):
            row["topic"] = term(detail["substage"], "glossary")
        # The catalogue marks the regulatory questions of a tool with yes/no flags, named by their codes.
        questions = []
        for flag, question in QUESTIONS.items():
            if str(entry.get(flag)).lower() == "true":
                questions.append(link(question))
        if questions:
            row["questions"] = questions
        if present(detail.get("doi")):
            cited = publication(detail["doi"])
            if cited:
                others.setdefault(cited["@id"], cited)
                row["doi"] = link(cited["@id"])
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
            row["license"] = web_link(written_license)
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
        # A level of technology readiness is written as TRL 4, TRL4, "TRL 8 - <its meaning>" or its number.
        if present(instance.get("TRL")):
            level = re.match(r"(?:TRL[\s-]*)?([1-9])\b", str(instance["TRL"]).strip(), re.IGNORECASE)
            row["trl"] = term("TRL " + level.group(1), "trl") if level else str(instance["TRL"])
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
                row[field] = [{"@type": kind, "title": title, "url": link(address)} for title, address in found]
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
            # A contact can name several people, and their emails, separated by ";".
            names = str(person["name"]).split(";")
            emails = str(person.get("email") or "").split(";")
            for position, name in enumerate(names):
                if not present(name):
                    continue
                identifier = "people/" + slug(name)
                row_of_person = {"@id": identifier, "@type": "Person", "name": name.strip()}
                email = emails[position] if position < len(emails) else ""
                if present(email):
                    row_of_person["email"] = email.strip()
                others.setdefault(identifier, row_of_person)
                maintainers.append(link(identifier))
        if maintainers:
            row["maintainer"] = maintainers
        rows.append(row)
    return rows + list(others.values())
