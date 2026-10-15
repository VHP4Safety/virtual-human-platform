# Linked data of the platform

The platform keeps its records (tools, methods, and the records they link to) in a SQLite
database, in the tables of the model's release: one table for each class of the application profile,
which `python -m linkeddata model` writes to `database/v1/tables.sql`. The model's SHACL shapes say
what a record holds, and pyshacl checks every record against them.
[rdfsolve](https://github.com/jmillanacosta/rdfsolve) converts the sources into the model, gives the
statements of a record as the rows of those tables, and makes the statements again from the rows.

```
source file ──parser──► clean rows ──lift──► RDF in the source's vocabulary
            ──rdfsolve rules──► RDF in the model ──pyshacl checks──► notes
            ──rdfsolve tables──► rows of the release's tables              python -m linkeddata import

API request ──JSON-LD──pyshacl checks──► rows and revision                 PUT, POST, DELETE /api/...
API query ──rows──rdfsolve from_tables──► JSON-LD, a page at a time            GET /api/...

page ──rows──rdfsolve from_tables──► JSON-LD, Turtle, N-Triples
```

## Run it

rdfsolve needs Python 3.12 or newer:

```
pip install -r requirements.txt -r linkeddata/requirements.txt
python -m linkeddata import     # fetches, converts and checks every source, and stores its records
python -m pytest tests          # checks the parts on small inputs, offline
```

`python -m linkeddata check` fails when a vocabulary file is not the pinned one, when `schema.json` or
`database/v1/tables.sql` is not what the vocabularies and `profile.ttl` give (after a change to the
profile, run `python -m linkeddata model`, review the change and commit it), or when the database's
tables are not those of the model's release. The Docker build runs it, and so does the container
before it starts the platform.

`import`, then `export` and `push`, are meant to run every night, for example with cron on the host:

```
0 3 * * *  docker exec platform python -m linkeddata import
30 3 * * * docker exec platform sh -c "python -m linkeddata export && python -m linkeddata push"
```

## The modules

The code is in four packages, each with one concern. Each uses only the packages listed before it,
except that `database/` reads the base address of records from `linkeddata/model.py`; the command line
(`linkeddata/__main__.py`), like `app.py`, uses them all.

| Package | Module | Concern |
|---|---|---|
| `database/` | `__init__.py`, `tables.py` | the database file and its tables (SQLAlchemy) |
| | `records.py` | reading records |
| | `images.py` | uploaded images: checked and saved again as WebP |
| | `export.py` | the records written on the platform, exported to a git repository |
| `linkeddata/` | `model.py`, `model/v1/` | the model and the application profile |
| | `parsers/`, `sources/` | how each source becomes the model |
| | `tables.py` | the release's tables: written from the profile, and records written to them and read from them with rdfsolve |
| | `rdf.py` | records as linked data and as JSON-LD, and the checks of a record against the model's shapes |
| | `imports.py` | the sources: fetched, converted and checked with rdfsolve, and stored as records |
| | `forms.py` | the editor's form of a class, read from the SHACL shapes and the application profile |
| | `quality.py` | how complete the records are, what the checks found, and how each source becomes the model |
| `admin/` | `accounts.py`, `tokens.py` | editors, and their write tokens |
| | `writes.py` | records written on the platform, each change with its revision |
| | `editor.py` | what the record editor shows for each kind of record |
| | `changes.py` | each change field by field, and as RDF statements |
| `routes/` | `pages.py` | the address of each record: its data, 410 Gone once removed, a general record page |
| | `data.py` | the `/data-quality` and `/sources` pages |
| | `api.py` | the API: records read a page at a time and filtered by their fields, and written |
| | `openapi.py` | the API's OpenAPI document, made from its routes, the profile, the vocabularies and the records |
| | `editor.py` | the record editor, a form that writes and removes records through the write API |
| | `changes.py` | the `/changes` pages |
| | `account.py` | the login of editors (ORCID, or a write token) and their tokens page |
| | `images.py` | the uploaded images, served |

## The database

| Table | Holds |
|---|---|
| `records` | one row per record, by its address (`iri`), with its class, its source (or `platform`) and its name |
| the release's tables | for each class of the profile, a table with a column for each field that takes one value and a column for its term (link, text, datatype or language); a table of the values of the fields that take several; and `statements`, for everything else |
| `revisions` | every change made on the platform: the record in JSON-LD before and after, who made it (name and ORCID iD) and when |
| `tokens` | the write tokens (only the hash of each secret) |
| `images` | the images uploaded to the platform, by the SHA-256 of their file, with who uploaded them |
| `sources` | for each source: its address, when it was fetched, its checksum, and the CONSTRUCT queries that convert it |
| `notes` | the values of the sources that do not fit the model, found by the checks of the imports; the records keep them as the sources give them |

The tables and their columns are named from the profile's CURIEs (`schema_software_application`,
`schema_name`, `dct_conforms_to`), so a term that stays the same from one release to the next keeps
its table or column. A value is kept as the source gives it, also when its kind does not fit the field,
and the checks note it. JSON-LD is compacted with the platform's context: schema.org terms have no
prefix (`name`), and the terms of other vocabularies keep theirs (`dct:conformsTo`).

## The application profile

`model/v1/profile.ttl` is the platform's application profile, written in SHACL. It says what the
platform asks of its records beyond schema.org and Bioschemas: which fields are required
(`sh:minCount`), which take one value (`sh:maxCount`), and which value the platform sets itself
(`sh:hasValue`, such as the Bioschemas profile of tools). Each write is checked against it with
pyshacl, after rdfsolve has checked the type of each value, and a refused write says what is wrong
with each field, in the words of the profile's `sh:message`.

The same profile leads the editor's form (`forms.py`): `sh:order`, `sh:name` and `sh:description`
place, name and explain each field, and `dash:singleLine false` asks for a longer text. What an
editor enters follows from the model: a text, a web address, a choice of the records that a field
links to (as checkboxes, grouped by the source of those records, and the terms of a vocabulary that
the profile lists with `sh:in`), or an image to upload. A field that
the profile does not describe is explained by the vocabulary. To change the form, change the profile.

## The parts of an import

- **`parsers/`: a temporary workaround.** The upstream files are not clean linked data (several
  values in one text, codes instead of addresses, placeholders). One parser per file cleans it and
  does nothing else. When the sources publish clean data, the parsers go. See `parsers/__init__.py`
  for what a parser returns.
- **`sources/<name>.yaml`**: where a source comes from (a `url`, or several named `files`), its
  title, its parser, and its rules: how its rows become the model. The rules are the arguments of rdfsolve's `Rule.between`, one list per kind of
  row; rdfsolve finds the fields by name and writes the CONSTRUCT queries.
- **`model/v1/`**: the model. `model.yaml` gives the base address of identifiers, the vocabularies
  (schema.org, the Bioschemas types and the VHP4Safety glossary, pinned with their SHA-256 and kept in
  `vocabularies/`), the classes by the name of their kind and the
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

3. Run the import, and check its records and notes on the `/sources` and `/data-quality` pages.

## Read records

`GET /api/<kind>` gives the records of each kind of `model.yaml` (tools, methods, questions,
organizations, people, pages, videos) in JSON-LD, a page at a time as a Hydra collection. Every field of
the kind is a query parameter, so `/api/tools?about=<step>&provider=<organisation>` gives the tools about
a step and provided by an organisation. `/api/notes` gives what the checks found, and `/api/sources` where
the records come from. `/api/openapi.json` describes the whole API in OpenAPI 3.1, and `/api/docs` shows
it: the document is made from the routes, the profile, the vocabularies and the records when it is asked
for, so it changes with them.

## Write records

Tools (the kinds listed under `writable` in `model/v1/model.yaml`) are written through the API with a
write token, as with ToxTempAssistant's workspace tokens. rdfsolve checks each record against the
model and the application profile, and the record and its revision are saved at once, so its page
shows it straight away. Every answer gives the address of the record and of its change.

```
PUT    /api/tools/aop-builder                  create or replace (the whole record)
POST   /api/tools                              create; the identifier is made from the name
DELETE /api/tools/aop-builder                  remove; the address answers 410 Gone and is not given again
DELETE /api/tools/aop-builder?permanent=true   remove the record and its address
POST   /api/images                             upload an image (form field "image"); gives its address
```

```
curl -X PUT https://platform.vhp4safety.nl/api/tools/aop-builder \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/json" \
     -d '{"name": "AOP-Builder", "description": "Builds AOPs from the literature.",
          "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

A refused record is answered with `422` and what is wrong with each field:
`{"error": "...", "fields": {"url": ["Add the address of the tool's website."]}}`. Only web addresses
(`https://` or `http://`) are kept as links. An uploaded image is read in full, made at most 2000
pixels wide, and saved again as WebP; other files are refused.

The record's data is at its address: `/tools/aop-builder.jsonld`, `.ttl` or `.nt`, or with the
`Accept` header. Its changes are at `/changes?record=<address>`.

The record editor, `/admin/`, writes with a form through the same API. Editors log in at `/login/`,
with ORCID or with a write token; the editor's requests carry the session's form token in the
`X-Form-Token` header, so that other sites cannot make them. Editors who logged in with ORCID make
tokens at `/account/tokens/`; the first token can be made with
`python -m linkeddata token <ORCID iD> "<name>" tools`. The settings are environment variables:

| Variable | Meaning |
|---|---|
| `PLATFORM_EDITORS` | the ORCID iDs of the editors, separated by commas |
| `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` | the platform's ORCID public API credentials; the redirect URI is `<platform>/orcid/callback/` |
| `SECRET_KEY` | the key that signs login sessions |
| `PLATFORM_STATE` | the folder of the database |
| `PLATFORM_RECORDS` | the records repository that `export` writes and `push` sends to its remote (for example `VHP4Safety/platform-data`) |
