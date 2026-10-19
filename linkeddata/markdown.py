"""Records in Markdown (RFC 7763), in GitHub's variant (RFC 7764), whose tables HTML texts may have: a heading for
the record and for each of its parts, a list of its fields, its HTML texts converted, the records that name it,
and the record's address, data and licence."""

from markdownify import markdownify

MEDIA = "text/markdown; charset=utf-8; variant=GFM"


def text(value: dict) -> str:
    if value["html"]:
        return markdownify(value["text"], heading_style="ATX", bullets="-").strip()
    return value["text"].strip()


def shown(value: dict) -> str:
    """A field's value: a link with its name (an address alone when it has none), or a text."""
    if "link" in value and value["name"] == value["link"]:
        return f"<{value['link']}>"
    if "link" in value:
        return f"[{value['name']}]({value['link']})"
    return text(value)


def values(field: dict) -> list[str]:
    found = []
    for value in field["values"]:
        found.append(shown(value))
    return found


def heading(level: int, title: str) -> str:
    """A heading; levels below the sixth are bold lines."""
    return "#" * level + " " + title if level <= 6 else f"**{title}**"


def node(found: dict, level: int) -> list[str]:
    lines = [heading(level, found["name"] or found["kind"])]
    if level > 1 and found["kind"]:
        lines.append(f"_{found['kind']}_" + (f" · <{found['address']}>" if found["address"] else ""))
    listed = []
    for field in found["fields"]:
        if field["long"]:
            lines.append(f"**{field['label']}**\n\n" + "\n\n".join(values(field)))
        else:
            listed.append(f"- **{field['label']}:** " + "; ".join(values(field)))
    if listed:
        lines.append("\n".join(listed))
    for group in found["parts"]:
        for item in group["items"]:
            lines.extend(node(item, level + 1))
    return lines


def record(found: dict, formats: dict[str, str], licence: str) -> str:
    """A record's outline in Markdown, with its address, its data in other formats (by name), and its licence."""
    lines = node(found, 1)
    lines.insert(1, f"<{found['address']}>")
    if found["named_on"]:
        named = []
        for label, holders in found["named_on"].items():
            links = []
            for holder in holders:
                links.append(f"{holder['kind']} [{holder['name']}]({holder['address']})" if holder["kind"] else f"[{holder['name']}]({holder['address']})")
            named.append(f"- **{label}:** " + "; ".join(links))
        lines.append(heading(2, "Named on other records") + "\n\n" + "\n".join(named))
    data = []
    for name, address in formats.items():
        data.append(f"[{name}]({address})")
    lines.append("---\n\nData: " + " · ".join(data) + f"  \nLicence: <{licence}>")
    return "\n\n".join(lines) + "\n"


def listing(title: str, rows: list[dict], licence: str) -> str:
    """Records as a list of links, each with its description."""
    lines = [heading(1, title)]
    listed = []
    for row in rows:
        described = f": {row['description']}" if row.get("description") else ""
        listed.append(f"- [{row['name']}]({row['address']}){described}")
    lines.append("\n".join(listed) if listed else "_None._")
    lines.append(f"---\n\nLicence: <{licence}>")
    return "\n\n".join(lines) + "\n"
