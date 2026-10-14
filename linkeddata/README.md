# Linked data of the platform

The platform keeps its records (tools, methods, and the glossary terms they link to) in a SQLite
database, through SQLAlchemy. [rdfsolve](https://github.com/jmillanacosta/rdfsolve) decides what fits
the platform's model: it converts the sources into records, checks every record written on the
platform, and makes the linked data of every page from the database's rows.

```
source file ──parser──► clean rows ──lift──► RDF in the source's vocabulary
            ──rdfsolve rules──► RDF in the model ──rdfsolve checks──► notes
            ──rdfsolve table──► rows of the records table                 python -m linkeddata import

API request ──rdfsolve from_table (checks)──► row and revision              PUT, POST, DELETE /api/...

page ──pandas read_sql──► rows ──rdfsolve from_table──► JSON-LD, Turtle, N-Triples
```

## Run it

rdfsolve needs Python 3.12 or newer:

```
pip install -r requirements.txt -r linkeddata/requirements.txt
python -m linkeddata import     # fetches, converts and checks every source, and stores its records
python -m pytest tests          # checks the parts on small inputs, offline
```

`import`, then `export` and `push`, are meant to run every night, for example with cron on the host:

```
0 3 * * *  docker exec platform python -m linkeddata import
30 3 * * * docker exec platform sh -c "python -m linkeddata export && python -m linkeddata push"
```

## The modules

Each module has one concern:

| Module | Concern |
|---|---|
| `database.py` | the tables of the database (SQLAlchemy) |
| `rdf.py` | rows as linked data and linked data as rows (pandas and rdfsolve) |
| `records.py` | reading records, and writing them on the platform with their revisions |
| `imports.py` | the sources: fetched, converted and checked with rdfsolve, and stored as records |
| `export.py` | the records written on the platform, exported to a git repository |
| `pages.py` | the address of each record: its data, 410 Gone once removed, a general record page |
| `dashboards.py` | the `/data-quality` and `/sources` pages |
| `api.py` | the write API |
| `tokens.py`, `accounts.py` | write tokens, and the ORCID login of editors |
| `model.py`, `model/v1/` | the model |
| `parsers/`, `lift.py`, `sources/` | how each source becomes the model |

## The database

| Table | Holds |
|---|---|
| `records` | one row per record, by its address (`iri`), with its class, its source (or `platform`), and one column per field |
| `revisions` | every change made on the platform: the record in JSON-LD, who made it (name and ORCID iD) and when |
| `tokens` | the write tokens (only the hash of each secret) |
| `sources` | for each source: its address, when it was fetched, its checksum, and the CONSTRUCT queries that convert it |
| `notes` | the values of the sources that do not fit the model, found by rdfsolve's checks; they are left out of the records |

The columns of `records` are fields of the model, named as rdfsolve names them (`conforms_to` for
`dct:conformsTo`); a field with several values is a JSON column. `rdf.py` asks rdfsolve which columns
are fields of a record's class, so to keep a new field it is enough to add its column in
`database.py` (and to an existing database with `ALTER TABLE records ADD COLUMN ...`).

## The parts of an import

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

An import replaces the records a source gave before with those it gives now. Records written on
the platform are left as they are, also when the source has a record at the same address.

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

3. Add a test with a few rows in `tests/test_imports.py`, and run the import.

## Write records

Tools (the kinds listed under `writable` in `model/v1/model.yaml`) are written through the API with a
write token, as with ToxTempAssistant's workspace tokens. rdfsolve checks each record against the
model, and the record and its revision are saved at once, so its page shows it straight away.

```
PUT    /api/tools/aop-builder                  create or replace (the whole record)
POST   /api/tools                              create; the identifier is made from the name
DELETE /api/tools/aop-builder                  remove; the address answers 410 Gone and is not given again
DELETE /api/tools/aop-builder?permanent=true   remove the record and its address
```

```
curl -X PUT https://platform.vhp4safety.nl/api/tools/aop-builder \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/json" \
     -d '{"name": "AOP-Builder", "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

The record's data is at its address: `/tools/aop-builder.jsonld`, `.ttl` or `.nt`, or with the
`Accept` header.

Editors log in with ORCID at `/login/orcid/` and make tokens at `/account/tokens/`; the first token
can be made with `python -m linkeddata token <ORCID iD> "<name>" tools`. The settings are environment
variables:

| Variable | Meaning |
|---|---|
| `PLATFORM_EDITORS` | the ORCID iDs of the editors, separated by commas |
| `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` | the platform's ORCID public API credentials; the redirect URI is `<platform>/orcid/callback/` |
| `SECRET_KEY` | the key that signs login sessions |
| `PLATFORM_STATE` | the folder of the database and of the sources' last downloads |
| `PLATFORM_RECORDS` | the records repository that `export` writes and `push` sends to its remote (for example `VHP4Safety/platform-data`) |
