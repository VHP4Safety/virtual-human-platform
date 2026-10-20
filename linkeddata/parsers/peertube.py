"""Parser of the VHP4Safety videos on video.edu.nl, a PeerTube site (a workaround, see linkeddata/parsers): the
account's list gives its videos, and each video's own answer its whole description.
- A video is a training material at training/<its name>, with its player as its video (its address, thumbnail
  and duration), its language, its licence (by name; "Unknown" is left out), its dates, its tags as keywords
  and the account's owner as its author, at organizations/<the owner's name>.
- Descriptions are Markdown, kept as text; durations are ISO 8601 (PT5M38S)."""

import json

from linkeddata.parsers import licence, link, present, slug, term

SITE = "https://video.edu.nl"
DATE = "http://www.w3.org/2001/XMLSchema#date"


def keys(index: bytes) -> list[str]:
    return [video["uuid"] for video in json.loads(index)["data"]]


def duration(seconds) -> str:
    """Seconds as an ISO 8601 duration: 338 is PT5M38S."""
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    written = "PT"
    for count, unit in ((hours, "H"), (minutes, "M"), (seconds, "S")):
        if count:
            written += f"{count}{unit}"
    return written if written != "PT" else "PT0S"


def parse(contents: dict[str, bytes]) -> list[dict]:
    rows = []
    for listed in json.loads(contents["peertube"])["data"]:
        video = json.loads(contents[listed["uuid"]]) if listed["uuid"] in contents else listed
        row = {"@id": "training/" + slug(video["name"]), "@type": "LearningResource", "name": video["name"],
               "description": video.get("description") or video.get("truncatedDescription"), "url": link(video["url"]),
               "learningResourceType": "video", "timeRequired": duration(video["duration"]),
               "video": {"@type": "VideoObject", "name": video["name"], "embedUrl": link(SITE + video["embedPath"]),
                         "thumbnailUrl": link(SITE + video["thumbnailPath"]), "duration": duration(video["duration"])}}
        language = (video.get("language") or {}).get("id")
        if present(language):
            row["inLanguage"] = language
        given = (video.get("licence") or {}).get("label")
        if present(given):
            row["license"] = licence(given)
        published = video.get("originallyPublishedAt") or video.get("publishedAt")
        if present(published):
            row["datePublished"] = {"@value": published[:10], "@type": DATE}
        if present(video.get("updatedAt")):
            row["dateModified"] = {"@value": video["updatedAt"][:10], "@type": DATE}
        row["keywords"] = [term(tag, "glossary") for tag in video.get("tags") or [] if present(tag)]
        owner = (video.get("account") or {}).get("displayName")
        if present(owner):
            row["author"] = link("organizations/" + slug(owner))
        rows.append(row)
    return rows
