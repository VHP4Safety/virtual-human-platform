# Linked data of the platform

Records are kept in SQLite, in the tables of the model's release:

- one table per class of the application profile;
- one table per field that takes several values.

The tables are written to `database/v1/tables.sql` by `python -m linkeddata model`; each row names its
record. Records are checked against the model's SHACL shapes with pyshacl. Sources are converted into the
model, and statements into rows and back, by [rdfsolve](https://github.com/jmillanacosta/rdfsolve).

```
source file ──parser──► clean rows ──lift──► RDF in the source's vocabulary
            ──rdfsolve rules──► RDF in the model ──pyshacl checks──► notes
            ──rdfsolve tables──► rows of the release's tables              python -m linkeddata import

API request ──JSON-LD──pyshacl checks──► rows and revision                 PUT, POST, DELETE /api/...
API query ──rows──rdfsolve from_tables──► JSON-LD, a page at a time            GET /api/...

page ──rows──rdfsolve from_tables──► JSON-LD, Turtle, N-Triples
```

## Run it

Python 3.12 or newer is needed by rdfsolve:

```
pip install -r requirements.txt -r linkeddata/requirements.txt
python -m linkeddata import     # every source is fetched, converted, checked and stored
python -m pytest tests          # the parts are checked on small inputs, offline
```

`python -m linkeddata check` fails when:

- a vocabulary file is not the pinned one;
- the profile uses a class or property that no pinned vocabulary defines;
- `database/v1/tables.sql` does not match the profile (after a profile change, `python -m linkeddata model`
  is run, and the change is reviewed and committed);
- the database's tables are not those of the model's release.

It is run by the Docker build, and by the container before the platform starts.

`import`, then `export` and `push`, are run nightly, such as with cron on the host:

```
0 3 * * *  docker exec platform python -m linkeddata import
30 3 * * * docker exec platform sh -c "python -m linkeddata export && python -m linkeddata push"
```

## The modules

The code is in four packages, one concern each. A package uses only those listed before it, except that
`database/` reads the base address of records from `linkeddata/model.py`. All are used by the command
line (`linkeddata/__main__.py`) and by `app.py`.

| Package | Module | Concern |
|---|---|---|
| `database/` | `__init__.py`, `tables.py` | the database file and its tables (SQLAlchemy) |
| | `records.py` | reading records |
| | `images.py` | uploaded images, checked and saved as WebP |
| | `export.py` | export of the platform's records to a git repository |
| `linkeddata/` | `model.py`, `model/v1/` | the model and the application profile |
| | `parsers/`, `sources/` | how each source becomes the model |
| | `storage.py` | statements as rows of the release's tables, with rdfsolve |
| | `documents.py` | records as JSON-LD documents, and as the dictionaries of page templates |
| | `checks.py` | checks of records against the model's shapes |
| | `imports.py` | sources fetched, converted and checked with rdfsolve, and stored as records |
| | `fields.py` | the fields of a class, from its shape in the profile |
| | `catalogue.py` | the records of a kind in SQL: filtered pages, and counts of each value |
| | `quality.py` | completeness, the checks' notes, and how each source becomes the model |
| `admin/` | `accounts.py`, `tokens.py` | editors and their write tokens |
| | `writes.py` | records written on the platform, each change with its revision |
| | `editor.py` | the editor's data: the records of each kind, and the graph of its forms |
| | `changes.py` | each change, field by field and as RDF statements |
| `routes/` | `record_pages.py` | each record's address: its data, 410 Gone once removed, a general record page |
| | `sources.py` | the `/sources` page |
| | `records_api.py` | the records API (flask-smorest): each record a graph of the W3C Graph Store Protocol |
| | `editor.py` | the record editor: forms built by shacl-form from the shapes, written through the records API |
| | `changes.py` | the `/changes` pages |
| | `account.py` | editor login (ORCID or a write token) and the tokens page |
| | `images.py` | uploaded images, served |

## The database

| Table | Holds |
|---|---|
| `records` | one row per record, by address (`iri`), with its class, source (or `platform`) and name; also one per part with an address, such as a case study question, with its record (`part_of`) |
| the release's tables | per class, a table with a column per single-valued field and one for its term (link, text, datatype or language); a table per field that takes several values; and `statements` for the rest. Each row names its record (`record`), parts included |
| `revisions` | every change made on the platform: the record in JSON-LD before and after, by whom (name and ORCID iD) and when |
| `tokens` | the write tokens (only each secret's hash) |
| `images` | uploaded images, by the SHA-256 of their file, with their uploader |
| `sources` | per source: its address, fetch time, checksum, and the CONSTRUCT queries that convert it |
| `notes` | source values that do not fit the model, found by the import checks; the records keep them as given |

Tables and columns are named from the profile's CURIEs (`schema_software_application`, `schema_name`,
`dct_conforms_to`), so a term kept between releases keeps its table or column. A value is kept as the
source gives it, also when its kind does not fit, and is noted by the checks. JSON-LD is compacted with the
platform's context: schema.org terms are unprefixed (`name`), and other vocabularies keep their prefixes
(`dct:conformsTo`).

## The application profile

`model/v1/profile/` is the platform's application profile, in SHACL, in modules: `ontology.ttl` (the
header), `text.ttl`, and one file per kind of record with the shapes of its parts (`tools.ttl`,
`casestudies.ttl`, `models.ttl`, ...). Each class has one node shape, named after it
(`form:SoftwareApplication`); its property shapes are the fields of its records. The profile sets:

- what each field takes (`sh:datatype`, `sh:nodeKind`, `sh:in`, `sh:class`, `sh:or`);
- required fields (`sh:minCount`) and single-valued ones (`sh:maxCount`);
- values that only warn when they do not fit (`sh:severity sh:Warning`).

Each write is checked against it with pyshacl, with rdfsolve's type checks from the vocabularies. A refused
write lists each field's problems, in the words of the profile's `sh:message`.

The records are also checked against the official Bioschemas shapes (`sh:shapesGraph` in the header, pinned as
the vocabularies are). The Bioschemas profile of a class is named on its node shape (`dct:conformsTo`); that
profile is stated on a record only when every field required by it is given, and the missing fields are noted on
the quality page. These results never refuse a write. The official schema.org shapes are not used: they are
recursive, so pyshacl stops on nested records, and any text is accepted by them for most fields.

The classes of the profile's node shapes with `form:path` are record classes (kinds); each record has its own
address and page. A node
of another class held through an `sh:node` field is part of its record, and is written with it:

- a page section has no address (`sh:nodeKind sh:BlankNode`);
- a case study question, or a workflow step, has one under the record's (`sh:nodeKind sh:IRI`,
  `/casestudies/kidney/Q1/exposure`).

Vocabulary terms, such as the VHP4Safety glossary's, are records at their own addresses
(`schema:DefinedTerm`, in a `schema:DefinedTermSet` at `/vocabularies/<name>`), so records can link to
them. The glossary's properties (Process Flow Step, Regulatory Question) are named in JSON-LD by their
`form:term` in the profile.

The editor's forms are built by shacl-form (`@ulb-darmstadt/shacl-form`) from the profile alone:

- each field is placed, named and explained by `sh:group`, `sh:order`, `sh:name` and `sh:description`;
- an `sh:node` field holds parts of the record;
- a field that links to records or terms (`sh:class`, or `sh:or` of classes) finds them by name with the
  API's search (`static/js/record-links.js`, a shacl-form plugin); a new record (a person, an
  organisation) or term can be added at once.

The form is changed by changing the profile. The profile's own terms:

- `form:path`, `sh:order` (on a node shape): the class's records are a kind, with pages at `/<path>/<name>`,
  in this order among the kinds;
- `sh:group`, `sh:order`, `sh:name`, `sh:description`: a field's section, place, label and help;
  `sh:message`: shown when a value is missing or does not fit; `dash:singleLine false`: a longer text;
- `form:private true`: kept off the pages and their data, shown to editors;
- `form:shown false`: kept in the data, not shown on the pages, shown to editors;
- `form:term`: the JSON-LD name of a property of another vocabulary, such as the glossary's;
- `form:publishedAs`: a class its values also have on the pages and their data, as schema.org expects (a
  licence is a CreativeWork); the records keep their own;
- `form:shows` (data, on a page section): the fields of the record the section presents (`schema:about`)
  that it shows.


## The parts of an import

- **`parsers/`: a temporary workaround.** Upstream files are not clean linked data (several values in one
  text, codes for addresses, placeholders). One parser per file cleans it, and nothing else. The parsers
  are removed once the sources publish clean data. What a parser returns is described in
  `parsers/__init__.py`.
- **`sources/<name>.yaml`**: a source's origin, title, parser and rules. The origin is one of:
  - a `url`, with `entries` for the file of each index key, or `terms` for one answer per term the records
    are about;
  - several named `files`;
  - a pinned `vocabulary` of the model;
  - for a source that `enriches` the records of a kind, the `answer` for each record's `identifier`.

  The rules are the arguments of rdfsolve's `Rule.between`, one list per kind of row; rdfsolve finds the
  fields by name and writes the CONSTRUCT queries. A source whose rows are shaped like other sources' names
  them (`uses`), and takes their rules.
- **`model/v1/`**: the model. `profile/` holds the one model, in modules: its header (`ontology.ttl`) gives the base address of
  identifiers (`void:uriSpace`), the vocabularies it is built from (`owl:imports`: schema.org, the Bioschemas
  types, VoID and the VHP4Safety glossary, each pinned by `form:file` and `form:sha256` and downloaded into `vocabularies/`
  when it is missing; the folder is not committed)
  and the prefixes of its JSON-LD (`sh:declare`); its shapes give the classes by kind (`form:path`) and what
  the platform adds to the vocabularies, such as its own PBPK terms.

An import:

- replaces a source's earlier records with its current ones; records written on the platform are kept,
  also at the same address, and so are records given by another source, such as a person named by two;
- runs the sources of terms after the others, and the sources that enrich records last;
- merges an enrichment into the other sources' records: a single-valued field keeps its value, and a
  different one is noted; a record's first enrichment is its first revision;
- checks each source's records against the model once every source is stored, with their linked records
  as stored; misfits are noted, and kept as given.

The sources:

- the tool and method catalogues of the cloud repository;
- the case studies of ui-casestudy-config;
- the VHP4Safety glossary (its pinned file);
- the datasets of the BioStudies collection VHP4Safety and of the Zenodo community vhp4safety;
- the ontology terms the records are about, with their ontologies, from the Ontology Lookup Service;
- the citations of the publications, from the DOI registration agencies (Crossref, DataCite) through
  doi.org.

## Add a source

1. Write `parsers/<name>.py`, with `parse(content: bytes) -> list[dict]` that only cleans the file.
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

3. Run the import; its records and notes are shown on `/sources` and on the data quality page (`/admin/quality`).

## Read and write records

The API is documented at `/api/docs/` (OpenAPI 3.1, by flask-smorest). A record body is JSON-LD with the
JSON-LD context of the platform (given on the `Record` schema as `x-jsonld-context`), or Turtle; the fields
are set by the shapes at `/api/shapes.ttl`. `{kind}` is one of the kinds of the profile.

- `GET /api/{kind}` lists the records of the kind, found by name (`search`) and by field values, by the
  name of the field (`/api/tools?processFlowStep=<address>&provider=<address>`). Several values of one
  field match any; several fields match all. A page is given at a time (`page`, `page_size`, and the
  `X-Pagination` header of flask-smorest), in JSON-LD (`@graph`, the default), Turtle or N-Triples, by the
  Accept header.
- `GET /api/{kind}/facets` counts the found records per value of those fields; the filter of a field is
  not used for its own counts. The queries are made in SQL from the rdfsolve layout of the profile
  (`catalogue.py`).
- `POST /api/{kind}` adds a record, at an address made from its name (a vocabulary term is at its own
  address, given as `@id`).
- `GET`, `PUT` and `DELETE /api/<address of its page>` (`/api/tools/aop-builder`,
  `/api/casestudies/kidney/Q1`) read a record in JSON-LD, Turtle, N-Triples or Markdown, add or replace
  it, and remove it. `POST /api/move` and `POST /api/restore` move and restore one. A part, such as a case
  study question, is read at its own address and written with its record.
- `GET /api/search?text=&class=&within=` finds records, their parts and vocabulary terms by name or
  address, for the editor and the pages.

Writes:

- are checked against the model's SHACL shapes (`/api/shapes.ttl`);
- need a write token or an editor's login;
- are refused with `412` when If-Match does not give the record's version (its ETag).

Each record's page address also answers in HTML, JSON-LD, Turtle or N-Triples, by the Accept header, and
links to its data, class and shapes with FAIR Signposting (Link headers).

## Write records

Records of every kind of the profile are written through the API with a write token, as with
ToxTempAssistant's workspace tokens. Each record is checked, then saved with its revision at once, so its
page shows it straight away. Each answer gives the addresses of the record and of its change.

```
curl -X PUT "https://platform.vhp4safety.nl/api/tools/aop-builder" \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/ld+json" \
     -d '{"@type": "SoftwareApplication", "name": "AOP-Builder", "description": "Builds AOPs from the literature.",
          "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

- A refused record is answered with `422`, flask-smorest's message, and each field's problems in
  `errors`.
- Only web addresses (`https://` or `http://`) are kept as links.
- An uploaded image (`POST /api/images`, form field `image`) is read in full, scaled to at most 2000
  pixels wide and saved as WebP; other files are refused.
- A record's changes are at `/changes?record=<address>`.

The record editor, `/admin/`, lists every kind of record and writes through the same API. Editors log in
at `/login/` with ORCID or a write token. The editor's requests carry the session's form token in the
`X-Form-Token` header, so other sites cannot make them. Tokens are made at `/account/tokens/` by editors
logged in with ORCID; the first one is made with `python -m linkeddata token <ORCID iD> "<name>" tools`.

The settings are environment variables:

| Variable | Meaning |
|---|---|
| `PLATFORM_EDITORS` | the editors' ORCID iDs, separated by commas |
| `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` | the platform's ORCID public API credentials; the redirect URI is `<platform>/orcid/callback/` |
| `SECRET_KEY` | the key that signs login sessions |
| `PLATFORM_STATE` | the database folder |
| `PLATFORM_RECORDS` | the records repository, written by `export` and pushed by `push` (such as `VHP4Safety/platform-data`) |
