# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python 3.12 or newer is needed (rdfsolve requires it).

```bash
pip install -r requirements.txt pytest
python patch.py                                      # once after the install: patches pyshexc
python app.py                                        # the platform on http://localhost:5050 (FLASK_DEBUG=1 for the reloader)
python -m pytest tests                               # offline, on a temporary database
python -m pytest tests/test_routes.py::test_pages    # one test
node tests/case-study.test.mjs                       # the case study renderer; Node 22 or newer, no dependencies
python -m linkeddata launch                          # once, on an empty database: fetch, convert, check and store all sources
python -m linkeddata import                          # the weekly sources
python -m linkeddata model                           # after a change of the profile: regenerate database/v1/tables.sql and the SHACL bundle
python -m linkeddata check                           # what the Docker build and the container run before the start
```

- There is no linter and no JavaScript toolchain (no `package.json`).
- CI builds the Docker image and runs CodeQL. It runs no tests, so run `pytest` and the Node check before a pull request.
- The state (SQLite database, backups) is in `instance/`, or in `PLATFORM_STATE`. A fresh checkout has no records until
  `launch`, which needs the network (set `GITHUB_TOKEN` to stay under the GitHub rate limit). For a deployment at
  another address, set `PLATFORM_BASE` before the launch: records are stored with their full addresses.

## Architecture

`linkeddata/README.md` is the reference for the data side. The short version:

- **Records are linked data.** Every tool, method, dataset, case study and site page is a record with an address. Records
  are stored in SQLite, in tables generated from the application profile (SHACL, `linkeddata/model/v1/`). rdfsolve
  converts between statements and rows, and pyshacl checks each write. A write is never refused for a value that does
  not fit: the problems come back as warnings and are kept as notes.
- **Four packages, each using only the ones before it:** `database/` (tables, records, images, export) →
  `linkeddata/` (profile, parsers, imports, documents, page content) → `admin/` (tokens, writes with revisions, editor
  data) → `routes/` (records API with flask-smorest, editor, changes, account). The pages of the website are routes
  of `app.py`.
- **Two kinds of sources.** `linkeddata/launch/` holds the sources that are read once, at launch (each a `.yaml` with
  its addresses and a parser). `linkeddata/sources/` with `linkeddata/parsers/` are imported each week. After the
  launch, launch-only records change through the editor or the API, not through their source.
- **One address, several formats.** A record address answers HTML, JSON-LD, Turtle, N-Triples or Markdown by content
  negotiation. `linkeddata/documents.py` makes the JSON-LD and `linkeddata/pages.py` the content of the pages.

### Case studies

A case study crosses the whole stack, and its page is drawn in the browser:

1. `linkeddata/launch/casestudies.py` reads `<case>_content.json` of `VHP4Safety/ui-casestudy-config` into one record: a
   study whose questions (`hasPart`) and steps (`step`) are `HowTo` pages, with the uses of tools, methods and data in
   `tool` and `supply`. `state: "disabled"` in the config becomes `creativeWorkStatus: "Incomplete"`.
2. `/casestudies/<case>/...` (every depth) serves `templates/case_studies/casestudy.html` with the JSON-LD of the
   record.
3. `static/js/case-study.js` draws everything from that document: breadcrumbs, the Process Flow header, the sliding
   pages, and the overview grid of a question (`layout()` places the pages, `overview()` draws them).

Levels are fixed: 0 the case study, 1 a question, 2 a workflow step, 3 a case study step, 4 and deeper a substep. A
page with `Incomplete` is greyed out and not opened. A page without content is hidden.

**The renderer has two callers.** The website gives it a nested document. The preview of the editor
(`templates/admin/records.html`, `static/js/editor.js`) gives it a flat document, in which steps are given by address
only, with `openDisabled` and `onPick`, and redraws it on every change of the form. A change to `case-study.js` has to
work in both. The preview does not load `static/css/base.css`; it loads `bootstrap-custom.css`, `editor.css`,
`casestudies.css` and `case-study.css`.

## Frontend conventions

- **Bootstrap 5 first.** Do it with Bootstrap utilities and components before writing CSS (see "CSS Styles" in
  `README.md`). The theme colours (`vhppink-distinct`, `vhpdarkpurple`, `vhpdarkteal`, `vhplightteal`, `vhpblue`,
  `vhplight-blue`, `vhplight-green`, ...) are theme colours of the custom build, so `btn-*`, `btn-outline-*`,
  `text-bg-*`, `bg-*` and `border-*` exist for each.
- **Global styles over page styles.** A layout decision belongs in `static/css/base.css` or in
  `bootstrap-custom/custom.scss`, not in a stylesheet of one page. Change an existing value before adding a rule.
- `static/css/bootstrap-custom.css` is compiled from `bootstrap-custom/custom.scss`:
  `cd bootstrap-custom && npm install bootstrap sass --save-dev && npx sass --load-path=node_modules custom.scss bootstrap-custom.css`,
  then move the result to `static/css/`.
- **No build step.** The scripts in `static/js` are ES modules, and libraries come from a CDN (Bootstrap 5.3.3 bundle,
  shacl-form, jsonld).
- **Style of the linked-data code and the renderer:** comments are full sentences that say what the code does, and
  the JavaScript uses `function` expressions with braces on every block, not arrow functions.

## Branches

- `pseudo` is the branch of the test site https://pseudo.platform.vhp4safety.nl. Every push to it publishes the
  `:pseudo` image (`.github/workflows/docker-publish.yml`), so changes go in through a pull request, not a direct push.
- The linked-data code (records, editor, case study renderer) may be on `pseudo` before it is on `main`. Check that the
  code you change exists on the branch you target.
- A release tag such as `1.0-5` publishes the versioned image.
