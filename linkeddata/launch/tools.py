"""Parser of the tools of the cloud catalogue."""

import json
import re

from linkeddata.parsers import QUESTIONS, licence, link, present, publication, slug, term, web_link

# This logo is used in the catalogue for tools without a logo.
PLACEHOLDER_LOGO = "https://github.com/VHP4Safety/ui-design/blob/main/static/images/logo.png"
LOGOS = "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/"
VHP4SAFETY = "organizations/vhp4safety"


def pairs(entry) -> list[tuple[str, str]]:
    """Return the titles and addresses of an entry such as {"title": "A;B", "url": "https://a;https://b"}."""
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
        row = {"@id": "tools/" + entry["id"], "@type": "SoftwareApplication", "name": entry["service"]}
        if present(entry.get("description")):
            row["description"] = entry["description"]
        if present(detail.get("url") or entry.get("main_url")):
            row["url"] = web_link(detail.get("url") or entry["main_url"])
        if present(instance.get("url")) and instance.get("url") != detail.get("url"):
            row["installUrl"] = web_link(instance["url"])
        logo = entry.get("png_file_name")
        if present(logo) and logo != PLACEHOLDER_LOGO:
            row["image"] = link(LOGOS + logo)
        # The stage is a process flow step, and the substage a topic: both are keywords of the glossary.
        if present(detail.get("stage") or entry.get("stage")):
            row.setdefault("keywords", []).append(web_link(detail.get("stage") or entry["stage"]))
        if present(detail.get("substage")):
            row.setdefault("keywords", []).append(term(detail["substage"], "glossary"))
        # Regulatory questions are yes/no flags named by their codes.
        questions = []
        for flag, question in QUESTIONS.items():
            if str(entry.get(flag)).lower() == "true":
                questions.append(link(question))
        # A tool used for a regulatory question is part of the toolbox of the question.
        if questions:
            row["isPartOf"] = questions
        if present(detail.get("doi")):
            cited = publication(detail["doi"])
            if cited:
                others.setdefault(cited["@id"], cited)
                row["citation"] = link(cited["@id"])
            else:
                row["citation"] = detail["doi"]
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
            row["sameAs"] = elsewhere
        if present(elixir.get("tess")):
            row.setdefault("keywords", []).extend(elixir["tess"] if isinstance(elixir["tess"], list) else [elixir["tess"]])
        if present(instance.get("version")):
            row["softwareVersion"] = str(instance["version"])
        notes = detail.get("notes") if isinstance(detail.get("notes"), dict) else {}
        written_license = instance.get("license") or detail.get("license") or notes.get("license")
        if present(written_license):
            row["license"] = licence(written_license)
        sources = []
        for address in (instance.get("source"), detail.get("source")):
            if present(address) and web_link(address) not in sources:
                sources.append(web_link(address))
        if sources:
            row["isBasedOn"] = sources
        downloads = []
        if present(instance.get("docker")):
            downloads.append(web_link(instance["docker"]))
        access = detail.get("access") if isinstance(detail.get("access"), dict) else {}
        packages = access.get("packages") if isinstance(access.get("packages"), dict) else {}
        for address in packages.values():
            if present(address):
                downloads.append(web_link(address))
        if downloads:
            row["downloadUrl"] = downloads
        # A readiness level is written as TRL 4, TRL4, "TRL 8 - <meaning>" or a number.
        if present(instance.get("TRL")):
            level = re.match(r"(?:TRL[\s-]*)?([1-9])\b", str(instance["TRL"]).strip(), re.IGNORECASE)
            row["creativeWorkStatus"] = term("TRL " + level.group(1), "trl") if level else str(instance["TRL"])
        if present(detail.get("release_notes")):
            row["releaseNotes"] = detail["release_notes"]
        help_pages = pairs(detail.get("intro")) + pairs(detail.get("demo"))
        deployment = detail.get("deployment_docs") or instance.get("deployment_docs")
        if present(deployment) and str(deployment).startswith(("http://", "https://")):
            help_pages.append(("Deployment guide", str(deployment)))
        for kind, address_field, field, found in (("WebPage", "url", "softwareHelp", help_pages),
                                                  ("WebPage", "url", "subjectOf", pairs(detail.get("workflow")) + pairs(detail.get("workflow2"))),
                                                  ("VideoObject", "embedUrl", "video", pairs(detail.get("peertube")))):
            if found:
                row[field] = [{"@type": kind, "name": title, address_field: link(address)} for title, address in found]
        provider = detail.get("provider") if isinstance(detail.get("provider"), dict) else {}
        contact = provider.get("contact") if isinstance(provider.get("contact"), dict) else {}
        # A contact with one of these names is linked to the record of that name, not added as a person.
        named = {slug("VHP4Safety"): VHP4SAFETY}
        providers = []
        if present(provider.get("name")):
            # In the catalogue template, the contact is described as a person, and the provider URL as the address of
            # an organisation. A provider with the name of its contact is one record: a person when no URL is given.
            if slug(provider["name"]) == slug(str(contact.get("name") or "")) and not present(provider.get("url")):
                identifier = "people/" + slug(provider["name"])
                others.setdefault(identifier, {"@id": identifier, "@type": "Person", "name": provider["name"].strip()})
            else:
                identifier = "organizations/" + slug(provider["name"])
                organization = {"@id": identifier, "@type": "Organization", "name": provider["name"]}
                if present(provider.get("url")):
                    organization["url"] = web_link(provider["url"])
                others.setdefault(identifier, organization)
            named[slug(provider["name"])] = identifier
            providers.append(link(identifier))
        # "development" means hosted by VHP4Safety. "External" and "independent" mean hosted elsewhere.
        if str(instance.get("vhp-platform") or "").strip().lower() == "development":
            providers.append(link(VHP4SAFETY))
        if providers:
            row["provider"] = providers
        if str(detail.get("developed-by-VHP")).lower() == "true":
            row["author"] = link(VHP4SAFETY)
        contacts = []
        if isinstance(provider.get("contact"), dict):
            contacts.append(provider["contact"])
        if isinstance(provider.get("additional_contacts"), list):
            contacts.extend(person for person in provider["additional_contacts"] if isinstance(person, dict))
        maintainers = []
        for person in contacts:
            if not present(person.get("name")):
                continue
            # Several people and emails can be given, separated by ";".
            names = str(person["name"]).split(";")
            emails = str(person.get("email") or "").split(";")
            for position, name in enumerate(names):
                if not present(name):
                    continue
                email = emails[position] if position < len(emails) else ""
                if slug(name) in named:
                    identifier = named[slug(name)]
                    if present(email):
                        others[identifier].setdefault("email", email.strip())
                elif "team" in name.lower():
                    # A team is an organisation, as for the authors of the documentation (docs.py).
                    identifier = "organizations/" + slug(name)
                    organization = {"@id": identifier, "@type": "Organization", "name": name.strip()}
                    if present(email):
                        organization["email"] = email.strip()
                    others.setdefault(identifier, organization)
                else:
                    identifier = "people/" + slug(name)
                    row_of_person = {"@id": identifier, "@type": "Person", "name": name.strip()}
                    if present(email):
                        row_of_person["email"] = email.strip()
                    others.setdefault(identifier, row_of_person)
                maintainers.append(link(identifier))
        if maintainers:
            row["maintainer"] = maintainers
        rows.append(row)
    return rows + list(others.values())
