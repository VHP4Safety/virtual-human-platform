"""Records in Markdown (RFC 7763, in GitHub's variant, RFC 7764), for agents and other readers of plain text: a
heading for the record and for each of its parts, its fields as a list or, when long, as paragraphs (HTML texts are
converted), and the record's address, data and licence."""

from markdownify import markdownify

MEDIA = "text/markdown; charset=utf-8; variant=GFM"


def shown(value: dict) -> str:
    """A value: a text, or a link with its name (an address alone when it has none)."""
    if "link" not in value:
        return markdownify(value["text"], heading_style="ATX", bullets="-").strip() if value["html"] else value["text"].strip()
    if value["name"] == value["link"]:
        return f"<{value['link']}>"
    return f"[{value['name']}]({value['link']})"


def node(found: dict, level: int) -> list[str]:
    """A record or a part: its heading (a bold line below the sixth level), its kind and address, and its fields."""
    title = found["name"] or found["kind"]
    lines = ["#" * level + " " + title if level <= 6 else f"**{title}**"]
    if level > 1 and found["kind"]:
        lines.append(f"_{found['kind']}_" + (f" · <{found['address']}>" if found["address"] else ""))
    listed = []
    for field in found["fields"]:
        values = [shown(value) for value in field["values"]]
        if field["long"]:
            lines.append(f"**{field['label']}**\n\n" + "\n\n".join(values))
        else:
            listed.append(f"- **{field['label']}:** " + "; ".join(values))
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
    data = " · ".join(f"[{name}]({address})" for name, address in formats.items())
    lines.append(f"---\n\nData: {data}" + (f"  \nLicence: <{licence}>" if licence else ""))
    return "\n\n".join(lines) + "\n"
