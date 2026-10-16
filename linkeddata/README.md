# Linked data of the platform

The platform keeps its records (tools, methods, and the records they link to) in a SQLite
database, in the tables of the model's release: one table for each class of the application profile,
and one for each of its fields that takes several values, which `python -m linkeddata model` writes to
`database/v1/tables.sql`. Every row names the record it belongs to. The model's SHACL shapes say
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
| | `storage.py` | where records are kept: their statements as rows of the release's tables, with rdfsolve |
| | `documents.py` | records as JSON-LD documents, and as the dictionaries that page templates read |
| | `checks.py` | the checks of records against the model's shapes |
| | `imports.py` | the sources: fetched, converted and checked with rdfsolve, and stored as records |
| | `fields.py` | the fields of a class, read from its shape in the application profile |
| | `catalogue.py` | the records of a kind in SQL: a page of those that have some values, and how many have each value |
| | `quality.py` | how complete the records are, what the checks found, and how each source becomes the model |
| `admin/` | `accounts.py`, `tokens.py` | editors, and their write tokens |
| | `writes.py` | records written on the platform, each change with its revision |
| | `editor.py` | what the record editor shows: the records of each kind, and the graph its forms are built from |
| | `changes.py` | each change field by field, and as RDF statements |
| `routes/` | `record_pages.py` | the address of each record: its data, 410 Gone once removed, a general record page |
| | `sources.py` | the `/sources` page |
| | `records_api.py` | the records API (flask-smorest): each record a graph of the W3C Graph Store Protocol |
| | `editor.py` | the record editor: shacl-form builds each form from the shapes, and writes through the records API |
| | `changes.py` | the `/changes` pages |
| | `account.py` | the login of editors (ORCID, or a write token) and their tokens page |
| | `images.py` | the uploaded images, served |

## The database

| Table | Holds |
|---|---|
| `records` | one row per record, by its address (`iri`), with its class, its source (or `platform`) and its name; and one per part of a record that has an address of its own, such as a question of a case study, with the record that holds it (`part_of`) |
| the release's tables | for each class of the profile, a table with a column for each field that takes one value and a column for its term (link, text, datatype or language); a table of the values of the fields that take several; and `statements`, for everything else. Every row names the record it belongs to (`record`), the rows of its parts too |
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

`model/v1/profile.ttl` is the platform's application profile, written in SHACL: one node shape for
each class, named after it (`form:SoftwareApplication`), whose property shapes are the fields of its
records. It says what each field takes (`sh:datatype`, `sh:nodeKind`, `sh:in`, `sh:class`, `sh:or`),
which fields are required (`sh:minCount`), which take one value (`sh:maxCount`), which value the
platform sets itself (`sh:hasValue`, such as the Bioschemas profile of tools), and which values only
warn when they do not fit (`sh:severity sh:Warning`). Each write is checked against it with pyshacl,
together with the type checks that rdfsolve gives from the vocabularies, and a refused write says what
is wrong with each field, in the words of the profile's `sh:message`.

The classes of `model.yaml`'s `kinds` are those of records, each with its own address and page. A node
of another class that a record holds through a field with `sh:node` is part of that record and is
written with it: a section of a page has no address (`sh:nodeKind sh:BlankNode`), and a question of a
case study, or a step of its workflow, has one under the record's (`sh:nodeKind sh:IRI`,
`/casestudies/kidney/Q1/exposure`). The terms of vocabularies, such as the VHP4Safety glossary's, are
records at their own addresses (`schema:DefinedTerm`, in a `schema:DefinedTermSet` at
`/vocabularies/<name>`), so that records link to them. The properties that the glossary defines (Process
Flow Step, Regulatory Question) are named in JSON-LD as `model.yaml`'s `terms` say.

The editor's forms are built by shacl-form (`@ulb-darmstadt/shacl-form`) from the profile alone:
`sh:group`, `sh:order`, `sh:name` and `sh:description` place, name and explain each field, and a field of
`sh:node` holds parts of the record. A field that links to records or terms (`sh:class`, or `sh:or` of
classes) finds them by name with the API's search (`static/js/record-links.js`, a shacl-form plugin), or
adds a new record (a person, an organisation) or registers a new term, at once. To change the form, change
the profile.

## The parts of an import

- **`parsers/`: a temporary workaround.** The upstream files are not clean linked data (several
  values in one text, codes instead of addresses, placeholders). One parser per file cleans it and
  does nothing else. When the sources publish clean data, the parsers go. See `parsers/__init__.py`
  for what a parser returns.
- **`sources/<name>.yaml`**: where a source comes from (a `url`, with `entries` for the file of each key
  of its index; several named `files`; or a pinned `vocabulary` of the model), its title, its parser, and
  its rules: how its rows become the model. The rules are the arguments of rdfsolve's `Rule.between`, one
  list per kind of row; rdfsolve finds the fields by name and writes the CONSTRUCT queries. A source whose
  rows are also those of other sources names them (`uses`), and has their rules too.
- **`model/v1/`**: the model. `model.yaml` gives the base address of identifiers, the vocabularies
  (schema.org, the Bioschemas types and the VHP4Safety glossary, pinned with their SHA-256 and kept in
  `vocabularies/`), the classes by the name of their kind and the
  prefixes; `profile.ttl` is what the platform adds to them; `schema.json` is the approved model,
  generated with `python -m linkeddata model` (review the change before committing it).

An import replaces the records a source gave before with those it gives now. Records written on
the platform are left as they are, also when the source has a record at the same address, and so are
those that another source gives, such as a person whom two sources name. Once every source is stored,
the records of each are checked against the model, with the records they link to as the database holds
them; what does not fit is noted, and kept as the source gives it.

The sources: the tool and method catalogues of the cloud repository, the case studies of
ui-casestudy-config, the VHP4Safety glossary (its pinned file), and the datasets of the BioStudies
collection VHP4Safety and of the Zenodo community vhp4safety.

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

3. Run the import, and check its records and notes on the `/sources` page and on the editor's data quality page (`/admin/quality`).

## Read and write records

The API is documented at `/api/docs/` (OpenAPI 3.1, written by flask-smorest; the record's schema carries
the JSON-LD context as `x-jsonld-context`). Each kind of record has a resource:

- `GET /api/<kind>` lists its records, found by name (`search`) and by the values of the fields it is
  browsed by: those of a closed list (`sh:in`, given as the parameter's enum) and the links to records or
  terms (`/api/tools?processFlowStep=<address>&provider=<address>`; several values of one field find the
  records with any of them, several fields the records with all). It answers a page at a time (`page`,
  `page_size`, and the `X-Pagination` header of flask-smorest) in JSON rows with the profile's field names,
  or in JSON-LD (`@graph`), Turtle or N-Triples, as Accept asks. `GET /api/<kind>/facets` counts how many of
  the records found have each value of those fields; a field's own filter is left out of its counts. The
  queries are made in SQL from rdfsolve's layout of the profile (`catalogue.py`).
- `POST /api/<kind>` adds a record, at an address made from its name (a term of a vocabulary is at its own
  address, given as `@id`).
- `GET`, `PUT` and `DELETE /api/<address of its page>` (`/api/tools/aop-builder`,
  `/api/casestudies/kidney/Q1`) read a record in JSON-LD, Turtle or N-Triples, add or replace it, and
  remove it; `POST /api/move` and `POST /api/restore` move and restore one. A part of a record, such as a
  question of a case study, is read at its own address and written with the record that holds it.
- `GET /api/search?text=&class=&within=` finds records, their parts and the terms of vocabularies by name
  or address, for the editor and the pages.

Writes are checked against the model's SHACL shapes (`/api/shapes.ttl`), need a write token or an editor's
login, and are refused with `412` when If-Match does not give the record's version (its ETag). The address
of each record's page also answers in HTML, JSON-LD, Turtle or N-Triples, as the Accept header asks, and
links to its data, its class and its shapes with FAIR Signposting (Link headers).

## Write records

Records of every kind of `model/v1/model.yaml` are written through the API with a
write token, as with ToxTempAssistant's workspace tokens. rdfsolve checks each record against the
model and the application profile, and the record and its revision are saved at once, so its page
shows it straight away. Every answer gives the address of the record and of its change.

```
curl -X PUT "https://platform.vhp4safety.nl/api/tools/aop-builder" \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/ld+json" \
     -d '{"@type": "SoftwareApplication", "name": "AOP-Builder", "description": "Builds AOPs from the literature.",
          "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

A refused record is answered with `422`, flask-smorest's message, and what is wrong with each field in
`errors`. Only web addresses (`https://` or `http://`) are kept as links. An uploaded image
(`POST /api/images`, form field `image`) is read in full, made at most 2000 pixels wide, and saved again as
WebP; other files are refused. A record's changes are at `/changes?record=<address>`.

The record editor, `/admin/`, lists every kind of record and writes through the same API. Editors log in at `/login/`,
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
