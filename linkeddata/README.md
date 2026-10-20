# Linked data of the platform

The records are stored in SQLite, in the tables of the release of the model:

- one table for each class of the application profile;
- one table for each field with several values.

The tables are written to `database/v1/tables.sql` with `python -m linkeddata model`. Each row names its record.
The records are checked against the SHACL shapes of the model with pyshacl. The sources are converted to the model,
and the statements to rows and back, with [rdfsolve](https://github.com/jmillanacosta/rdfsolve).

```
source file ──parser──► rows in the terms of the model ──JSON-LD──► RDF ──pyshacl checks──► notes
            ──rdfsolve tables──► rows of the release tables                python -m linkeddata import

API request ──JSON-LD──pyshacl checks──► rows and revision                 PUT, POST, DELETE /api/...
API query ──rows──rdfsolve from_tables──► JSON-LD, one page at a time        GET /api/...

page ──rows──rdfsolve from_tables──► JSON-LD, Turtle, N-Triples
```

## Run it

Python 3.12 or newer is required by rdfsolve.

```
pip install -r requirements.txt -r linkeddata/requirements.txt
python -m linkeddata launch     # once: fetch, convert, check and store all sources
python -m linkeddata import     # each week: fetch, convert, check and store the weekly sources
python -m pytest tests          # check the parts on small inputs, offline
```

`python -m linkeddata check` fails in these cases:

- a vocabulary file is not the pinned file;
- the profile uses a class or a property that is not defined in a pinned vocabulary;
- `database/v1/tables.sql` does not match the profile. After a change of the profile, run
  `python -m linkeddata model`, then review and commit the change;
- the tables of the database are not the tables of the release of the model.

The check is run by the Docker build, and by the container before the platform starts.

Run `import`, then `export` and `push`, each week, for example with cron:

```
0 3 * * 1  docker exec platform python -m linkeddata import
30 3 * * 1 docker exec platform sh -c "python -m linkeddata export && python -m linkeddata push"
```

## The modules

The code is in four packages, with one concern each. A package uses only the packages listed before it, except that
`database/` reads the profile from `linkeddata/profile.py`. All packages are used by the command line
(`linkeddata/__main__.py`) and by `app.py`.

| Package | Module | Concern |
|---|---|---|
| `database/` | `__init__.py`, `tables.py` | the database file and its tables (SQLAlchemy) |
| | `records.py` | reads and writes of records as rows of the release tables (rdfsolve), listing pages and facets |
| | `images.py` | uploaded images, checked and stored as WebP |
| | `export.py` | export of the platform records to a git repository |
| `linkeddata/` | `profile.py`, `model/v1/` | the model, the application profile and the fields of each class |
| | `parsers/`, `sources/` | the conversion of each source to the model |
| | `launch/` | the sources that are read once, at launch, and the corrections made then |
| | `documents.py` | JSON-LD documents of the records |
| | `pages.py` | the content of the record pages, the listings and the home page |
| | `checks.py` | checks of the records against the shapes, and the data quality page |
| | `imports.py` | imports of the sources: fetch, conversion with rdfsolve, checks and storage |
| | `crates.py` | the RO-Crate of each record |
| | `void.py` | the VoID description of the data of the platform |
| `admin/` | `tokens.py` | write tokens and editor sign-ins |
| | `writes.py` | writes of records on the platform, with a revision for each change |
| | `editor.py` | the data of the editor: the records of each kind, and the graph of the forms |
| | `changes.py` | the comparison of a record before and after a change |
| `routes/` | `record_pages.py` | the address of each record: its page, its data, 410 Gone after removal |
| | `records_api.py` | the records API (flask-smorest), with each record as a graph of the W3C Graph Store Protocol |
| | `editor.py` | the record editor (forms made by shacl-form from the shapes) and the data quality page |
| | `changes.py` | the `/changes` pages |
| | `account.py` | editor sign-in (ORCID or a write token) and the tokens page |
| | `discovery.py` | `/.well-known/api-catalog` and `/.well-known/void` |
| | `images.py` | the uploaded images |

## The database

| Table | Content |
|---|---|
| `records` | one row for each record, by address (`iri`), with its class, source (or `platform`) and name; also one row for each part with an address, such as a case study question, with its record (`part_of`) |
| release tables | for each class, a table with a column for each single-valued field and one for its term (link, text, datatype or language); a table for each field with several values; and `statements` for the other statements. Each row names its record (`record`), also for parts |
| `revisions` | each change made on the platform: the record in JSON-LD before and after the change, the editor (name and ORCID iD) and the time |
| `tokens` | the write tokens, with the hash of each secret only |
| `images` | the uploaded images, by the SHA-256 of their file, with their uploader |
| `sources` | for each source: its addresses, the time of the last fetch, the checksum, and the problem of the last import if it failed |
| `notes` | the values that do not fit the model, as found by the checks; the records keep these values as given |

The tables and the columns are named from the CURIEs of the profile (`schema_software_application`, `schema_name`,
`dct_conforms_to`), so a term that is kept between releases keeps its table or column. A value is kept as given in
the source, also if its kind does not fit, and it is noted by the checks. The JSON-LD is compacted with the context
of the platform: schema.org terms have no prefix (`name`), and other vocabularies keep their prefixes
(`dct:conformsTo`).

## The application profile

`model/v1/profile/` is the application profile of the platform, in SHACL, in modules: `ontology.ttl` (the header),
`text.ttl`, and one file for each kind of record with the shapes of its parts (`tools.ttl`, `casestudies.ttl`,
`models.ttl`, ...). Each class has one node shape, named after the class (`form:SoftwareApplication`). Its property
shapes are the fields of its records. The profile sets:

- the values of each field (`sh:datatype`, `sh:nodeKind`, `sh:in`, `sh:class`, `sh:or`);
- the required fields (`sh:minCount`) and the single-valued fields (`sh:maxCount`);
- the values that only give a warning if they do not fit (`sh:severity sh:Warning`).

Each write is checked against the profile with pyshacl, with the type checks of rdfsolve from the vocabularies. A
write is not stopped by problems. The problems are returned as warnings for each field, with the `sh:message` of
the profile.

The records are also checked against the official Bioschemas shapes (`sh:shapesGraph` in the header, pinned as the
vocabularies are). The Bioschemas profile of a class is named on its node shape (`dct:conformsTo`), and only these
profiles are checked. The profile is stated on a record (`dct:conformsTo`) only if all fields required by it are
given. The results of an official shape are reported only for the fields of the form. The fields of a declared
profile that the model does not have are listed on the data quality page. The official schema.org shapes are not
used: they are recursive, so pyshacl stops on nested records, and they accept any text for most fields.

The classes of the node shapes with `form:path` are record classes (kinds). Each record has its own address and
page. A node of another class in an `sh:node` field is a part of its record, and it is written with its record:

- a page section has no address (`sh:nodeKind sh:BlankNode`);
- a case study question, or a workflow step, has an address under the address of the record (`sh:nodeKind sh:IRI`,
  `/casestudies/kidney/Q1/exposure`).

Vocabulary terms, such as the terms of the VHP4Safety glossary, are records at their own addresses
(`schema:DefinedTerm`, in a `schema:DefinedTermSet` at `/vocabularies/<name>`), so that records can link to them.
The properties of the glossary (Process Flow Step, Regulatory Question) are named in JSON-LD by their `form:term` in
the profile.

The forms of the editor are made by shacl-form (`@ulb-darmstadt/shacl-form`) from the profile only:

- each field is placed, named and explained by `sh:group`, `sh:order`, `sh:name` and `sh:description`;
- an `sh:node` field has parts of the record;
- in a field with links to records or terms (`sh:class`, or `sh:or` of classes), the records and terms are found by
  name with the search of the API (`static/js/record-links.js`, a shacl-form plugin). A new record (a person, an
  organisation) or term can be added at once.

To change the form, change the profile. The terms of the profile:

- `form:path`, `sh:order` (on a node shape): the records of the class are a kind, with pages at `/<path>/<name>`, in
  this order among the kinds;
- `sh:group`, `sh:order`, `sh:name`, `sh:description`: the section, place, label and help of a field; `sh:message`:
  the text shown if a value is missing or does not fit; `dash:singleLine false`: a longer text;
- `form:private true`: not shown on the pages and not in their data; shown to editors;
- `form:shown false`: kept in the data, not shown on the pages; shown to editors;
- `form:term`: the JSON-LD name of a property of another vocabulary, such as a property of the glossary;
- `form:publishedAs`: an additional class of the values on the pages and in their data, as expected by schema.org
  (a licence is a CreativeWork); the records keep their own class;
- `form:shows` (data, on a page section): the fields of the presented record (`schema:about`) that are shown in the
  section.

## The parts of an import

- **`parsers/`: a temporary workaround.** Upstream files are not clean linked data (several values in one text,
  codes for addresses, placeholders). One parser for each file cleans the file, and does nothing else. Remove a
  parser when its source publishes clean data. The rows of a parser are described in `parsers/__init__.py`.
- **`sources/<name>.yaml`**: the origin, the title and the parser of a source. The origin is one of these:
  - a `url`, with `entries` for the file of each index key, or `terms` for one response for each term of the
    records;
  - several named `files`;
  - a pinned `vocabulary` of the model;
  - for a source that `enriches` the records of a kind, the `answer` for the `identifier` of each record.
- **`launch/`**: the sources that are read once, with `python -m linkeddata launch`, with their parsers, and the
  corrections of `launch.yaml`. The pinned vocabularies change only with a new pin, so they are also read at launch.
  A launch is refused on a database with imported records.
- **`model/v1/`**: the model. `profile/` has the one model, in modules. Its header (`ontology.ttl`) has the base
  address of the identifiers (`void:uriSpace`, replaced by `PLATFORM_BASE` if it is set), the vocabularies of the
  model (`owl:imports`: schema.org, the Bioschemas types, VoID and the VHP4Safety glossary, each pinned by
  `form:file` and `form:sha256` and downloaded into `vocabularies/` if missing; this folder is not committed), and
  the prefixes of the JSON-LD (`sh:declare`). Its shapes give the classes by kind (`form:path`), and the additions
  of the platform to the vocabularies, such as its own PBPK terms.

At an import:

- the earlier records of a source are replaced with its current records. Records written on the platform are kept,
  also at the same address, and so are the records of another source, such as a person named in two sources;
- the sources of terms are imported after the other sources, and the sources that enrich records last;
- an enrichment is merged into the records of the other sources. A single-valued field keeps its value, and a
  different value is noted. The first enrichment of a record is its first revision;
- the records of each source are checked against the model once all sources are stored, with their linked records
  as stored. Misfits are noted, and kept as given.

The sources:

- the tool and method catalogues of the cloud repository;
- the case studies of ui-casestudy-config;
- the VHP4Safety glossary (its pinned file);
- the datasets of the BioStudies collection VHP4Safety and of the Zenodo community vhp4safety;
- the models of the Zenodo community vhp4safety, from their RO-Crates;
- the training materials: the tutorials of the documentation, the courses on GitHub and the videos on PeerTube;
- the ontology terms of the records, with their ontologies, from the Ontology Lookup Service;
- the citations of the publications, from the DOI registration agencies (Crossref, DataCite) through doi.org;
- the organisations, matched in the Research Organization Registry, and the grants, from NWOpen.

## Add a source

1. Write `parsers/<name>.py`, with `parse(content: bytes) -> list[dict]` that only cleans the file.
2. Write `sources/<name>.yaml`:

```yaml
name: zenodo
title: Zenodo community vhp4safety
url: https://zenodo.org/api/records?communities=vhp4safety&type=dataset&size=25&sort=newest
parser: zenodo
```

3. Run the import. The notes of its records are shown on the data quality page (`/admin/quality`).

## Read and write records

The API is documented at `/api/docs/` (OpenAPI 3.1, made with flask-smorest). A record body is JSON-LD with the
JSON-LD context of the platform (on the `Record` schema as `x-jsonld-context`), or Turtle. The fields are described
in the shapes at `/api/shapes.ttl`. `{kind}` is one of the kinds of the profile.

- `GET /api/{kind}`: list the records of the kind, found by name (`search`) and by field values, with the name of
  the field (`/api/tools?processFlowStep=<address>&provider=<address>`). Several values of one field match any of
  them; several fields must all match. One page is returned at a time (`page`, `page_size`, and the `X-Pagination`
  header of flask-smorest), in JSON-LD (`@graph`, the default), Turtle, N-Triples or Markdown, as requested in the
  Accept header.
- `GET /api/{kind}/facets`: count the found records for each value of those fields. The filter of a field is not
  applied to its own counts. The queries are made in SQL from the rdfsolve layout of the profile
  (`database/records.py`).
- `POST /api/{kind}`: add a record, at an address made from its name (a vocabulary term is stored at its own
  address, given as `@id`).
- `GET`, `PUT` and `DELETE /api/<page address>` (`/api/tools/aop-builder`, `/api/casestudies/kidney/Q1`): read a
  record in JSON-LD, Turtle, N-Triples or Markdown, add or replace it, and remove it. `POST /api/move` and
  `POST /api/restore`: move and restore a record. A part, such as a case study question, is read at its own address
  and written with its record.
- `GET /api/search?text=&class=&within=`: find records, their parts and vocabulary terms by name or address, for
  the editor and the pages.

Writes:

- are checked against the SHACL shapes of the model (`/api/shapes.ttl`), and are stored with the problems as
  warnings;
- require a write token or the sign-in of an editor;
- are refused with `412` if the version in If-Match (the ETag of the record) is not the current version.

The page address of each record also returns HTML, JSON-LD, Turtle or N-Triples, as requested in the Accept header,
with links to its data, class and shapes in FAIR Signposting (Link headers).

## Write records

Records of all kinds of the profile are written through the API with a write token, as with the workspace tokens
of ToxTempAssistant. Each record is checked, then stored with its revision at once, so that its page is updated
immediately. The response has the addresses of the record and of its change.

```
curl -X PUT "https://platform.vhp4safety.nl/api/tools/aop-builder" \
     -H "Authorization: Bearer vhp_..." -H "Content-Type: application/ld+json" \
     -d '{"@type": "SoftwareApplication", "name": "AOP-Builder", "description": "Builds AOPs from the literature.",
          "url": {"@id": "https://github.com/VHP4Safety/aop-builder"}}'
```

- A record that does not fit the shapes is stored. The problems of each field are returned in `warnings`.
- A link that is not a web address (`https://` or `http://`) is refused with `422`.
- An uploaded image (`POST /api/images`, form field `image`) is read in full, scaled to at most 2000 pixels on its
  longest side and stored as WebP. Other files are refused.
- The changes of a record are listed at `/changes?record=<address>`.

The record editor, at `/admin/`, lists all kinds of records, and writes through the same API. Editors sign in at
`/login/` with ORCID or with a write token. The requests of the editor are sent with the form token of the session
in the `X-Form-Token` header, which cannot be sent by other sites. Tokens are made at `/account/tokens/` by editors
signed in with ORCID. Make the first token with `python -m linkeddata token <ORCID iD> "<name>" tools`.

The settings are environment variables:

| Variable | Meaning |
|---|---|
| `PLATFORM_EDITORS` | the ORCID iDs of the editors, separated by commas |
| `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` | the credentials of the platform for the ORCID public API; the redirect URI is `<platform>/orcid/callback/` |
| `SECRET_KEY` | the key that signs the sign-in sessions |
| `PLATFORM_STATE` | the folder of the database |
| `PLATFORM_BASE` | the base address of a deployment at another address, such as `https://pseudo.platform.vhp4safety.nl/`. It replaces the base address of the profile (`void:uriSpace`). The records are stored with their full addresses, so set it before `launch` and do not change it after |
| `PLATFORM_RECORDS` | the records repository, written with `export` and pushed with `push` (such as `VHP4Safety/platform-data`) |
