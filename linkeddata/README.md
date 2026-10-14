# Linked data of the platform

The platform's data is converted into an RDF model with [rdfsolve](https://github.com/jmillanacosta/rdfsolve)
and written to `build/`: an Oxigraph store with one named graph per source, and a SQLite file with one
JSON-LD document per page. The web app only reads them.

```
upstream file ──parser──► clean rows ──lift──► RDF in the source's vocabulary
              ──rdfsolve rules──► RDF in the model ──rdfsolve checks──► notes
              ──► build/rdf (Oxigraph)  +  build/platform.sqlite (JSON-LD per page)
```

## Run it

The build needs Python 3.12 or newer (for rdfsolve):

```
pip install -r linkeddata/requirements.txt
python -m linkeddata build      # fetches every source, converts, checks and writes build/
python -m pytest tests          # checks parsers, rules and output on small inputs, offline
```

`build/platform.sqlite` has three tables:

| Table | Holds |
|---|---|
| `documents` | one JSON-LD document per page, by its address (`iri`) and type |
| `sources` | for each source: its address, when it was downloaded, its checksum, and the CONSTRUCT queries that converted it |
| `notes` | the values that do not fit the model, as reported by rdfsolve's checks |

## The parts

- **`parsers/`: a temporary workaround.** The upstream files are not clean linked data (several
  values in one text, codes instead of addresses, placeholders). One parser per file cleans it and
  does nothing else. When the sources publish clean data, the parsers go. See `parsers/__init__.py`
  for what a parser returns.
- **`lift.py`**: turns clean rows into RDF in the source's own vocabulary (a JSON-LD `@vocab`),
  until rdfsolve reads JSON with a context itself.
- **`sources/<name>.yaml`**: where a source comes from, its parser, and its rules: how its rows
  become the model. The rules are the arguments of rdfsolve's `Rule.between`, one list per kind of
  row; rdfsolve finds the fields by name and writes the CONSTRUCT queries. A source that is sent to
  the platform instead of fetched (`toxtemp.yaml`) has no `url` and no parser; its `kinds` name the
  kind of the objects under each key of its documents.
- **`model/v1/`**: the model. `model.yaml` gives the base address of identifiers, the vocabularies
  (schema.org and the Bioschemas types, pinned and kept in `vocabularies/`), the classes and the
  prefixes; `profile.ttl` is what the platform adds to them; `schema.json` is the approved model,
  generated with `python -m linkeddata model` (review the change before committing it).
- **`build.py`**: runs the parts in order. rdfsolve mines each source, runs its rules, mines the
  result, and checks every class of the model against the model's shapes.

## Add a source

1. Write `parsers/<name>.py` with `parse(content: bytes) -> list[dict]` that only cleans the file.
2. Write `sources/<name>.yaml`:

```yaml
name: tools
url: https://raw.githubusercontent.com/VHP4Safety/cloud/refs/heads/main/cap/service_index.json
parser: tools
rules:
  Tool:                                                    # the "@type" of the parsed rows
    - {predicate: a, value: "https://schema.org/SoftwareApplication"}
    - {predicate: "https://schema.org/name", object: service}   # the rows' "service" field
```

3. Add a test with a few rows in `tests/test_linkeddata.py`, and run the build.

## Write records

Tools (the kinds listed under `writable` in `model/v1/model.yaml`) are written through the API with a
write token, as with ToxTempAssistant's workspace tokens. rdfsolve checks each record against the
model; the record is kept as a JSON-LD file in the records repository, at the path of its page
(`tools/aop-builder.jsonld`), and every change is one commit. A record written this way replaces
what a source gives for the same address. After a write, the build runs again in the background
with the sources downloaded by the last build.

```
PUT    /api/tools/aop-builder                  create or replace (the whole record)
POST   /api/tools                              create; the identifier is made from the name
DELETE /api/tools/aop-builder                  remove; the address stays gone
DELETE /api/tools/aop-builder?permanent=true   remove the record and its address
```

```
curl -X PUT https://platform.vhp4safety.nl/api/tools/aop-builder \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/json" \
     -d '{"name": "AOP-Builder", "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

Editors log in with ORCID at `/login/orcid/` and make tokens at `/account/tokens/`; the first token
can be made with `python -m linkeddata token <ORCID iD> "<name>" tools`. The settings are environment
variables:

| Variable | Meaning |
|---|---|
| `PLATFORM_EDITORS` | the ORCID iDs of the editors, separated by commas |
| `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` | the platform's ORCID public API credentials; the redirect URI is `<platform>/orcid/callback/` |
| `SECRET_KEY` | the key that signs login sessions |
| `PLATFORM_RECORDS`, `PLATFORM_STATE`, `PLATFORM_BUILD` | the records repository, the tokens, and the built files |

`python -m linkeddata push` sends the records repository to its remote (for example
`VHP4Safety/platform-data`); it is meant to run every night.
