// shacl-form plugins of the record editor.
import { Plugin, registerPlugin, findLabel, loadRDF } from "https://cdn.jsdelivr.net/npm/@ulb-darmstadt/shacl-form@3.7.3/dist/bundle.js";
import { busy } from "./busy.js";
import { GLOSSARY, draftBody, openRequest, tableChoice } from "./glossary.js";

const IRI = "http://www.w3.org/ns/shacl#IRI";
const LABEL = "http://www.w3.org/2000/01/rdf-schema#label";
const IS_DEFINED_BY = "http://www.w3.org/2000/01/rdf-schema#isDefinedBy";
const TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const TARGET = "http://www.w3.org/ns/shacl#targetClass";
const CLASS = "http://www.w3.org/ns/shacl#class";
const FIRST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#first";
const REST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest";
const NAME = "https://schema.org/name";
const TERM = "https://schema.org/DefinedTerm";
const IN_SET = "https://schema.org/inDefinedTermSet";
// The namespace of a vocabulary, with its name in the API.
const SPACE = "void:uriSpace";
const STRING = "http://www.w3.org/2001/XMLSchema#string";
const HTML = "http://www.w3.org/1999/02/22-rdf-syntax-ns#HTML";
const editor = JSON.parse(document.getElementById("editor").textContent);
let vocabularyList = null;

// The style of the plugins. The page styles are not applied in the shadow root of the form. Shown inputs are as wide
// as the .editor inputs.
const STYLE = `
.shown:not([type='checkbox']) { flex-grow: 1; }
textarea.shown { resize: vertical; }
.text-edit { align-self: flex-start; margin-left: 6px; padding: 3px 12px; border: 0; border-radius: 4px; background: #29235c; color: #fff; font-size: 0.85em; cursor: pointer; white-space: nowrap; }
.record-link-box { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.record-link-row { display: flex; align-items: center; gap: 6px; }
.record-link-row > .shown { flex: 1; min-width: 0; }
.record-link-kind { font-size: 0.75em; padding: 1px 6px; border-radius: 4px; background: #e7e5f2; color: #29235c; white-space: nowrap; }
.record-link-kind.text { background: #fff3cd; color: #664d03; }
.record-link-kind:empty, .record-link-open[hidden] { display: none; }
.record-link-open { color: #29235c; text-decoration: none; padding: 0 4px; }
.record-link-options { display: flex; flex-direction: column; border: 1px solid #ccc; border-top: 0; max-height: 16em; overflow-y: auto; }
.record-link-options:empty { display: none; }
.record-link-options button { display: flex; align-items: center; gap: 6px; text-align: left; background: #fff; border: 0; border-bottom: 1px solid #eee; padding: 4px 8px; font: inherit; cursor: pointer; }
.record-link-options button:hover { background: #f1f0f7; }
.record-link-options .record-link-new { font-weight: 600; color: #29235c; }
.record-link-problem { padding: 4px 8px; color: #b02a37; }
.record-link-busy { padding: 4px 8px; color: #6c757d; }
.record-link-busy::before { content: ""; display: inline-block; width: 0.8em; height: 0.8em; margin-right: 6px; vertical-align: -0.1em; border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%; animation: record-link-turning 0.75s linear infinite; }
@keyframes record-link-turning { to { transform: rotate(360deg); } }
.record-link-vocabulary { margin-bottom: 4px; font: inherit; }
.record-link-add { font-size: 0.75em; padding: 1px 8px; border: 1px solid #198754; border-radius: 4px; background: #fff; color: #146c43; white-space: nowrap; cursor: pointer; }
.record-link-add:hover { background: #d1e7dd; }
.record-link-add[hidden] { display: none; }
.record-link-options .record-link-draft { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 6px 8px; border-bottom: 1px solid #eee; }
.record-link-options .record-link-draft button { border: 1px solid #ccc; border-radius: 4px; }
.record-link-options .record-link-draft .record-link-problem, .record-link-options .record-link-draft .record-link-note { flex-basis: 100%; padding: 0; }
.record-link-label { font-size: 0.85em; color: #495057; }
.record-link-table { font: inherit; }
.record-link-note { font-size: 0.85em; color: #6c757d; }
shacl-node, rokit-collapsible { scroll-margin-top: 1rem; }
.index-shown { outline: 3px solid var(--bs-vhppink, #e6007e); outline-offset: 4px; border-radius: 0.25rem; }
/* An open group grows with its fields. The max-height set by rokit-collapsible at the time of opening is removed. */
rokit-collapsible[open]::part(content) { max-height: none !important; }
.value-type { align-self: center; margin-left: 4px; padding: 0 4px; border: 1px solid #ced4da; border-radius: 3px; color: #6c757d; font: 0.7em monospace; white-space: nowrap; }
`;

async function api(method, address, body) {
  const response = await fetch(address, {
    method: method,
    credentials: "same-origin",
    headers: { "X-Form-Token": editor.token, "Content-Type": "application/json", Accept: "application/ld+json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const answer = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    throw new Error(answer.detail || answer.message || response.statusText);
  }
  return answer;
}

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className || "";
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// Return a platform address as an address on this server, so that the link is valid on each copy.
function local(iri) {
  return iri.startsWith(editor.base) ? "/" + iri.slice(editor.base.length) : iri;
}

// Return a text as a quoted literal for shacl-form, with its datatype unless it is plain (such as rdf:HTML).
function literal(text, datatype) {
  return '"' + text + '"' + (datatype && datatype !== STRING ? "^^" + datatype : "");
}

function query(fields) {
  return Object.entries(fields).map(function (entry) { return entry[0] + "=" + encodeURIComponent(entry[1]); }).join("&");
}

// A text field of the theme, with the value as a literal of the datatype of the field for shacl-form. An address in a
// text field is kept until the text is edited.
// TinyMCE, loaded when a text is edited for the first time.
const TINYMCE = "https://cdn.jsdelivr.net/npm/tinymce@6.8.5";
let tinymceLoaded = null;

function loadTinymce() {
  tinymceLoaded = tinymceLoaded || new Promise(function (resolve, reject) {
    const script = document.createElement("script");
    script.src = TINYMCE + "/tinymce.min.js";
    script.onload = function () { resolve(window.tinymce); };
    script.onerror = function () { reject(new Error("The text editor could not be loaded.")); };
    document.head.append(script);
  });
  return tinymceLoaded;
}

// Edit an HTML text in a dialog, and call done with the new HTML.
async function editText(label, html, done) {
  // A box over the page, not a modal <dialog>, so that the dialogs of TinyMCE are drawn above it.
  const overlay = document.createElement("div");
  overlay.className = "text-overlay";
  const dialog = document.createElement("div");
  dialog.className = "text-dialog";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-label", "Edit text: " + label);
  overlay.append(dialog);
  const head = document.createElement("div");
  head.className = "text-dialog-head";
  head.textContent = "Edit text: " + label;
  // While the text is edited, platform addresses, such as the addresses of uploaded images, are opened on this
  // server, so that they are valid on each copy of the platform. In the text, they are kept as platform addresses.
  const here = window.location.origin + "/";
  const area = document.createElement("textarea");
  area.value = (html || "").split(editor.base).join(here);
  const foot = document.createElement("div");
  foot.className = "text-dialog-foot";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn btn-light border";
  cancel.textContent = "Cancel";
  const ready = document.createElement("button");
  ready.type = "button";
  ready.className = "btn btn-vhppurple";
  ready.textContent = "Done";
  foot.append(cancel, ready);
  dialog.append(head, area, foot);
  document.body.append(overlay);
  const tinymce = await loadTinymce();
  const [text] = await tinymce.init({
    target: area,
    base_url: TINYMCE,
    suffix: ".min",
    height: "calc(100vh - 12rem)",
    menubar: false,
    branding: false,
    promotion: false,
    plugins: "image link lists table code",
    toolbar: "undo redo | blocks | bold italic | bullist numlist | link image table | code",
    block_formats: "Paragraph=p; Heading=h3; Smaller heading=h4",
    image_caption: true,
    image_title: true,
    automatic_uploads: true,
    images_file_types: "png,jpg,jpeg,webp,gif",
    convert_urls: false,
    images_upload_handler: async function (blob) {
      const body = new FormData();
      body.append("image", blob.blob(), blob.filename());
      const answer = await fetch("/api/images", { method: "POST", credentials: "same-origin", headers: { "X-Form-Token": editor.token }, body: body });
      const given = await answer.json().catch(function () { return {}; });
      if (!answer.ok) {
        throw new Error(given.message || "The image was not uploaded.");
      }
      return given["@id"].split(editor.base).join(here);
    },
  });
  function close() {
    text.remove();
    overlay.remove();
  }
  cancel.addEventListener("click", close);
  ready.addEventListener("click", function () {
    const html = text.getContent().split(here).join(editor.base);
    close();
    done(html);
  });
}

class Text extends Plugin {
  createEditor(template, value) {
    if (template.in) {
      return choice(template, value);
    }
    const datatype = template.datatype ? template.datatype.value : STRING;
    const field = template.config.theme.createTextEditor(template.label, value || null, false, template);
    const shown = field.querySelector(".editor");
    shown.classList.replace("editor", "shown");
    const text = document.createElement("input");
    text.type = "hidden";
    text.className = "editor";
    if (value && value.termType === "NamedNode") {
      text.dataset.nodeKind = IRI;
      text.value = value.value;
    } else {
      text.value = shown.value ? literal(shown.value, datatype) : "";
    }
    field.append(text);
    shown.addEventListener("input", function () {
      delete text.dataset.nodeKind;
      text.value = shown.value ? literal(shown.value, datatype) : "";
    });
    // A long text, which may have HTML, is edited in the text editor, and its HTML is shown in the box below. It is kept as
    // a plain text, and the pages show its markup.
    if (datatype === HTML || editor.long.includes(template.path)) {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "text-edit";
      edit.textContent = "Edit text";
      edit.addEventListener("click", function () {
        // The title of the dialog is the name of the part of the text, such as the heading of a section.
        const node = field.closest("shacl-node");
        let named = "";
        for (const found of node ? node.querySelectorAll('.property-instance[data-path="' + NAME + '"]') : []) {
          if (found.closest("shacl-node") === node) {
            const input = found.querySelector(".shown") || found.querySelector(".editor");
            named = input ? String(input.value || "").trim() : "";
            break;
          }
        }
        editText(named || template.label, shown.value, function (html) {
          shown.value = html;
          shown.dispatchEvent(new Event("input"));
          shown.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
        });
      });
      field.append(edit);
    }
    return field;
  }
}

// Open a dialog with a title, a place for refusals and a body. Remove it when it is closed.
function opened(title) {
  const dialog = make("dialog", "record-dialog");
  const top = make("div", "d-flex align-items-center gap-2 border-bottom px-3 py-2");
  const close = make("button", "btn-close");
  close.type = "button";
  close.setAttribute("aria-label", "Close");
  close.addEventListener("click", function () { dialog.close(); });
  top.append(make("h2", "h5 mb-0 me-auto", title), close);
  const refused = make("div", "alert alert-danger small mx-3 mt-3 mb-0 d-none");
  const body = make("div", "p-3");
  dialog.append(top, refused, body);
  dialog.addEventListener("close", function () { dialog.remove(); });
  document.body.append(dialog);
  dialog.showModal();
  return {
    dialog: dialog,
    body: body,
    refuse: function (text) {
      refused.textContent = text;
      refused.classList.remove("d-none");
    },
  };
}

function labelled(text, input) {
  const label = make("label", "form-label small mb-1 d-block", text);
  label.append(input);
  return label;
}

// Add a new record in a dialog form made from the shape of its class, and pass it to added.
function addRecord(of_class, label, name, store, added) {
  const shape = store.getSubjects(TARGET, of_class, null)[0];
  const subject = "urn:uuid:" + crypto.randomUUID();
  const shown = opened("New " + label.toLowerCase());
  const form = document.createElement("shacl-form");
  form.dataset.shapesUrl = document.querySelector("shacl-form").dataset.shapesUrl;
  form.dataset.shapeSubject = shape ? shape.value : "";
  form.dataset.valuesSubject = subject;
  form.dataset.values = "<" + subject + "> a <" + of_class + "> ; <" + NAME + "> " + JSON.stringify(name) + " .";
  form.dataset.generateNodeShapeReference = "";
  form.dataset.collapse = "open";
  // The record is added if the checks of the platform accept it, as in the form of the editor.
  const add = make("button", "btn btn-success", "Add the " + label.toLowerCase());
  add.type = "button";
  add.addEventListener("click", async function () {
    const working = busy(add, "Adding…", shown.body);
    try {
      const response = await fetch("/api/" + editor.classes[of_class], {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-Form-Token": editor.token, "Content-Type": "text/turtle", Accept: "application/json" },
        body: form.serialize("text/turtle"),
      });
      const answer = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        throw new Error(answer.detail || answer.message || response.statusText);
      }
      const record = await api("GET", "/api" + local(answer["@id"]));
      shown.dialog.close();
      added(answer["@id"], record.name || name);
    } catch (error) {
      working.done();
      shown.refuse(error.message);
    }
  });
  const bar = make("div", "editor-save mt-3");
  bar.append(add);
  shown.body.append(form, bar);
}

// Add a vocabulary from a registry, or one entered by hand.
async function addVocabulary(platform, added) {
  const shown = opened("Add a vocabulary");
  const registry = make("select", "form-select form-select-sm");
  for (const [name, title] of Object.entries(await api("GET", "/api/registries"))) {
    registry.append(new Option(title, name));
  }
  registry.append(new Option("By hand", ""));
  const text = make("input", "form-control form-control-sm");
  text.placeholder = "Name, such as assay or BAO";
  const searchButton = make("button", "btn btn-outline-secondary btn-sm", "Search");
  searchButton.type = "button";
  const asking = make("div", "input-group input-group-sm");
  asking.append(text, searchButton);
  const results = make("div", "list-group list-group-flush border rounded small record-dialog-results");
  const name = make("input", "form-control form-control-sm");
  name.placeholder = "Name, such as NCBI Taxonomy";
  const namespace = make("input", "form-control form-control-sm");
  namespace.placeholder = "Term address start, such as http://purl.obolibrary.org/obo/NCBITaxon_";
  const add = make("button", "btn btn-success btn-sm mt-2", "Add the vocabulary");
  add.type = "button";
  const finding = make("div", "");
  finding.append(labelled("Name", asking), results);
  const writing = make("div", "d-none");
  writing.append(labelled("Name", name), labelled("Namespace", namespace), add);
  shown.body.append(labelled("Registry", registry), finding, writing);

  async function keep(found, button) {
    for (const vocabulary of platform) {
      if (found.namespace && vocabulary[SPACE] === found.namespace) {
        shown.dialog.close();
        added(vocabulary["@id"]);
        return;
      }
    }
    const working = busy(button, "Adding…", shown.body);
    try {
      const body = { name: found.title };
      if (found.namespace) {
        body[SPACE] = found.namespace;
      }
      if (found.description) {
        body.description = found.description;
      }
      const answer = await api("POST", "/api/vocabularies", body);
      shown.dialog.close();
      added(answer["@id"]);
    } catch (error) {
      working.done();
      shown.refuse(error.message);
    }
  }

  let asked = 0;
  function shownPart() {
    finding.classList.toggle("d-none", !registry.value);
    writing.classList.toggle("d-none", Boolean(registry.value));
    results.replaceChildren();
  }
  // The registry is searched once for each click of Search or Enter.
  async function find() {
    shownPart();
    if (!registry.value) {
      return;
    }
    // Only the latest response is shown.
    asked += 1;
    const question = asked;
    const searching = make("div", "list-group-item text-secondary");
    searching.append(make("span", "spinner-border spinner-border-sm me-1"), document.createTextNode("Searching…"));
    results.append(searching);
    try {
      const answer = await api("GET", "/api/registries/" + registry.value + "/vocabularies?" + query({ text: text.value.trim() }));
      if (question !== asked) {
        return;
      }
      results.replaceChildren();
      if (!answer.length) {
        results.append(make("div", "list-group-item text-secondary", "No vocabulary found."));
      }
      for (const found of answer) {
        const item = make("button", "list-group-item list-group-item-action");
        item.type = "button";
        item.append(make("b", "", found.title), make("div", "text-secondary", found.id + " · " + found.namespace));
        item.addEventListener("click", function () { keep(found, item); });
        results.append(item);
      }
    } catch (error) {
      results.replaceChildren();
      shown.refuse(error.message);
    }
  }
  registry.addEventListener("change", shownPart);
  searchButton.addEventListener("click", find);
  text.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      find();
    }
  });
  add.addEventListener("click", function () {
    keep({ title: name.value.trim(), namespace: namespace.value.trim() }, add);
  });
  shownPart();
}

// Register a term by hand, with label and address, in a platform vocabulary.
function registerTerm(text, vocabulary, added) {
  const shown = opened("Register a term of " + vocabulary.name);
  const label = make("input", "form-control form-control-sm");
  label.value = text;
  const address = make("input", "form-control form-control-sm");
  address.value = vocabulary[SPACE] || "";
  const add = make("button", "btn btn-success btn-sm mt-2", "Register the term");
  add.type = "button";
  add.addEventListener("click", async function () {
    const working = busy(add, "Registering…", shown.body);
    try {
      const answer = await api("POST", "/api/terms", { "@id": address.value.trim(), name: label.value.trim(), inDefinedTermSet: { "@id": vocabulary["@id"] } });
      shown.dialog.close();
      added(answer["@id"], label.value.trim());
    } catch (error) {
      working.done();
      shown.refuse(error.message);
    }
  });
  shown.body.append(labelled("Label", label), labelled("Address", address), add);
}

// Store a draft term for the VHP4Safety glossary, and open the term request form if asked.
function proposeTerm(text, vocabulary, added) {
  const shown = opened("Propose a term for " + vocabulary.name);
  const label = make("input", "form-control form-control-sm");
  label.value = text;
  const abbreviation = make("input", "form-control form-control-sm");
  const definition = make("textarea", "form-control form-control-sm");
  definition.rows = 3;
  const references = make("textarea", "form-control form-control-sm");
  references.rows = 2;
  references.placeholder = "Web addresses of the sources of the definition, one on each line";
  const table = tableChoice();
  const draft = make("button", "btn btn-outline-success btn-sm", "Use as a draft");
  const request = make("button", "btn btn-success btn-sm", "Use as a draft, and request it on GitHub");
  draft.type = "button";
  request.type = "button";

  async function store(button, asked) {
    const term = {
      name: label.value.trim(),
      abbreviation: abbreviation.value.trim(),
      definition: definition.value.trim(),
      references: references.value.split(/\s+/).filter(function (given) { return /^https?:\/\//.test(given); }),
    };
    if (!term.name) {
      shown.refuse("A label is needed.");
      return;
    }
    if (!table.value) {
      shown.refuse("Choose the table of the glossary that the term goes to.");
      return;
    }
    if (asked) {
      openRequest(term, table.value);
    }
    const working = busy(button, "Storing…", shown.body);
    try {
      const answer = await api("POST", "/api/terms", draftBody(term, vocabulary, table.value, editor.person));
      shown.dialog.close();
      added(answer["@id"], term.name);
    } catch (error) {
      working.done();
      shown.refuse(error.message);
    }
  }
  draft.addEventListener("click", function () { store(draft, false); });
  request.addEventListener("click", function () { store(request, true); });
  const bar = make("div", "d-flex flex-wrap gap-2 mt-2");
  bar.append(draft, request);
  shown.body.append(
    make("p", "small text-secondary", "The term is stored as a draft at a platform address, and can be used at once. The glossary repository proposes it in the chosen table each day, with you as its contributor, and gives its glossary address when the proposal is accepted."),
    labelled("Label", label), labelled("Abbreviation", abbreviation), labelled("Definition", definition),
    labelled("References", references), labelled("Table of the glossary", table), bar);
}

// The earlier values of each link field while the form is open, by node and property, so that a removed value is put
// back as it was, a text as a text and a link with its name.
const held = new Map();

function hold(field, path, entry) {
  const node = field.closest("shacl-node");
  const scope = (node ? node.dataset.nodeId : "") + " " + path;
  if (!held.has(scope)) {
    held.set(scope, new Map());
  }
  held.get(scope).set((entry.text ? "text " : "link ") + entry.value, entry);
  return scope;
}

// Draw a field with a list of values as a choice by label.
function choice(template, value) {
  const store = template.config.store;
  const entries = [];
  // The list is identified by its first node. In the store, a node without an address is named "_:...".
  const start = String(template.in);
  for (let node = start.includes(":") ? start : "_:" + start; node; ) {
    const item = store.getObjects(node, FIRST, null)[0];
    if (!item) {
      break;
    }
    // The label of a vocabulary term, without the kind of term in brackets ("Exposure (Process Flow Step)").
    const label = (store.getObjects(item, LABEL, null)[0] || item).value.replace(/\s*\([^)]*\)$/, "");
    entries.push({ value: item, label: label });
    const rest = store.getObjects(node, REST, null)[0];
    node = rest && rest.termType !== "NamedNode" ? rest : null;
  }
  return template.config.theme.createListEditor(template.label, value || null, false, entries, template);
}

// Return the classes of a link field by name, from its own shape.
function linkClasses(template) {
  const store = template.config.store;
  const named = editor.links[template.path] || {};
  const found = {};
  if (template.class) {
    found[template.class.value] = named[template.class.value] || template.class.value.split(/[/#]/).pop();
  }
  for (const alternative of template.or || []) {
    const given = store.getObjects(alternative, CLASS, null)[0];
    if (given) {
      const label = store.getObjects(alternative, LABEL, null)[0];
      found[given.value] = label ? label.value : named[given.value] || given.value.split(/[/#]/).pop();
    }
  }
  return Object.keys(found).length ? found : named;
}

class RecordLink extends Plugin {
  createEditor(template, value) {
    if (template.in) {
      return choice(template, value);
    }
    // The link classes of the field by name, from the profile. Text fields, such as tool keywords, have none.
    // In a field with a choice of a link or another value, the other value, such as an address, is shown as text.
    const linking = template.class || (template.or && !editor.mixed.includes(template.path));
    const classes = linking ? linkClasses(template) : {};
    const names = Object.values(classes);
    if (!names.length) {
      return Text.prototype.createEditor.call(this, template, value);
    }
    const store = template.config.store;
    const field = template.config.theme.createTextEditor(template.label, null, false, template);
    const search = field.querySelector(".editor");
    search.classList.replace("editor", "shown");
    search.pattern = undefined;
    search.setAttribute("placeholder", "Find a " + names.join(" or a ").toLowerCase() + " by name");
    const kind = make("span", "record-link-kind");
    const open = make("a", "record-link-open", "↗");
    open.target = "_blank";
    open.rel = "noopener";
    open.title = "Open page";
    // A text in a term field is added to the chosen vocabulary with one button.
    const adding = make("button", "record-link-add");
    adding.type = "button";
    adding.hidden = true;
    // The link, read by shacl-form as the value. A text in a link field is kept until a record is chosen.
    const chosen = document.createElement("input");
    chosen.type = "hidden";
    chosen.className = "editor";
    if (value && value.termType === "Literal") {
      chosen.value = literal(value.value);
      search.value = value.value;
    } else if (value) {
      chosen.dataset.nodeKind = IRI;
      chosen.value = value.value;
      search.value = findLabel(store.getQuads(value.value, null, null, null), template.config.languages) || value.value;
    }
    // The value is kept once the field is in the form, where its node is known.
    if (value) {
      const loaded = { text: value.termType === "Literal", value: value.value, name: search.value };
      window.requestAnimationFrame(function () { hold(field, template.path, loaded); });
    }
    const options = make("div", "record-link-options");
    const row = make("div", "record-link-row");
    const box = make("div", "record-link-box");
    search.replaceWith(box);
    row.append(kind, search, adding, open);
    box.append(row, options);
    field.append(chosen);

    // Show the kind and the page of the linked record. A text in a term field has the button that adds it to the
    // chosen vocabulary.
    function show() {
      kind.className = "record-link-kind";
      kind.textContent = "";
      kind.title = "";
      open.hidden = true;
      adding.hidden = true;
      if (!chosen.value) {
        return;
      }
      if (chosen.dataset.nodeKind !== IRI) {
        kind.classList.add("text");
        kind.textContent = "Text";
        kind.title = "Name only: find or add its record";
        if (classes[TERM] && vocabulary && search.value.trim()) {
          adding.textContent = "＋ Add to " + vocabulary.name;
          adding.title = "Add “" + search.value.trim() + "” as a term of " + vocabulary.name + ", and link it here";
          adding.hidden = false;
        }
        return;
      }
      let named = "";
      let fits = false;
      for (const type of store.getObjects(chosen.value, TYPE, null)) {
        if (classes[type.value]) {
          named = classes[type.value];
          fits = true;
        } else if (!named && editor.classes[type.value]) {
          named = editor.classes[type.value];
        }
      }
      kind.textContent = named || "Elsewhere";
      if (!fits) {
        kind.classList.add("text");
        kind.title = named ? "Wrong kind" : "Not a platform record";
      }
      open.href = local(chosen.value);
      open.hidden = false;
    }

    function choose(iri, name) {
      chosen.dataset.nodeKind = IRI;
      chosen.value = iri;
      search.value = name;
      options.replaceChildren();
      show();
      hold(field, template.path, { text: false, value: iri, name: name });
      chosen.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function putBack(entry) {
      if (!entry.text) {
        choose(entry.value, entry.name);
        return;
      }
      delete chosen.dataset.nodeKind;
      chosen.value = literal(entry.value);
      search.value = entry.value;
      options.replaceChildren();
      show();
      chosen.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Return the earlier values of this field that it no longer has, with the text in their name.
    function heldOptions(text) {
      const present = new Set();
      const property = field.closest("shacl-property");
      for (const input of property ? property.querySelectorAll("input.editor") : []) {
        present.add(input.value);
      }
      const node = field.closest("shacl-node");
      for (const entry of (held.get((node ? node.dataset.nodeId : "") + " " + template.path) || new Map()).values()) {
        const given = entry.text ? literal(entry.value) : entry.value;
        if (!present.has(given) && entry.name.toLowerCase().includes(text.toLowerCase())) {
          option([make("span", "record-link-kind text", "↺ Put back"), entry.name], function () { putBack(entry); });
        }
      }
    }

    function option(content, onClick, className) {
      const button = make("button", className || "");
      button.type = "button";
      button.append(...content);
      button.addEventListener("click", onClick);
      // Options are listed above the search that is still running.
      options.insertBefore(button, options.querySelector(".record-link-busy"));
    }

    // Add the new records and terms also to the graph of the form, for the checks of the form.
    async function known(iri, name, of_class) {
      store.addQuads(await loadRDF({ rdf: "<" + iri + "> a <" + of_class + "> ; <" + LABEL + "> " + JSON.stringify(name) + " ." }));
      choose(iri, name);
    }

    async function attempt(action) {
      try {
        await action();
      } catch (error) {
        options.replaceChildren(make("div", "record-link-problem", error.message));
      }
    }

    // In a term field, a vocabulary is chosen first, and terms are found in its namespace.
    let vocabulary = null;
    if (classes[TERM]) {
      const vocabularies = make("select", "record-link-vocabulary");
      box.prepend(vocabularies);
      let listed = [];
      const fill = async function (selected) {
        // The vocabularies are requested once, for all the term fields of the page.
        vocabularyList = vocabularyList || api("GET", "/api/vocabularies?page_size=200");
        listed = (await vocabularyList)["@graph"];
        vocabularies.replaceChildren();
        for (const found of listed) {
          vocabularies.append(new Option(found.name, found["@id"], false, found["@id"] === selected));
        }
        vocabularies.append(new Option("Add a vocabulary…", ""));
        // A kept term is shown in its own vocabulary, else in the vocabulary whose namespace starts its address. For
        // a field of one vocabulary (sh:pattern ^<namespace>), only that vocabulary is shown.
        const only = template.pattern && template.pattern.startsWith("^") ? template.pattern.slice(1).replace(/\\(.)/g, "$1") : "";
        const own = value ? store.getObjects(value.value, IN_SET, null).map(function (found) { return found.value; }) : [];
        const current = listed.find(function (found) {
          const space = found[SPACE];
          return (only && space === only) || own.includes(found["@id"]) || (value && space && value.value.startsWith(space));
        });
        if (current && !selected) {
          vocabularies.value = current["@id"];
        } else if (value && !selected) {
          vocabularies.prepend(new Option("Not in a platform vocabulary", "none", true, true));
        } else if (!selected) {
          vocabularies.prepend(new Option("Any vocabulary", "any", true, true));
        }
        vocabularies.disabled = Boolean(only && current);
        vocabulary = listed.find(function (found) { return found["@id"] === vocabularies.value; }) || null;
        show();
      };
      vocabularies.addEventListener("change", function () {
        vocabulary = listed.find(function (found) { return found["@id"] === vocabularies.value; }) || null;
        options.replaceChildren();
        show();
        if (vocabularies.value) {
          return;
        }
        attempt(function () {
          return addVocabulary(listed, function (iri) { vocabularyList = null; attempt(function () { return fill(iri); }); });
        });
      });
      attempt(function () { return fill(null); });
    }

    // Add the text of the field to the chosen vocabulary, and link the new term in its place. A draft term of the
    // glossary needs the table that it goes to. A term of another vocabulary is found in the registry of the
    // vocabulary, or registered by hand.
    function addDirectly() {
      const text = search.value.trim();
      if (!text || !vocabulary) {
        return;
      }
      options.replaceChildren();
      if (vocabulary[SPACE] === GLOSSARY) {
        const panel = make("div", "record-link-draft");
        const table = tableChoice();
        table.className = "record-link-table";
        table.setAttribute("aria-label", "Table of the glossary");
        const store = make("button", "record-link-new", "Add “" + text + "” as a draft term");
        store.type = "button";
        const more = make("button", "", "More fields…");
        more.type = "button";
        store.addEventListener("click", function () {
          if (!table.value) {
            table.focus();
            panel.querySelector(".record-link-problem") || panel.append(make("div", "record-link-problem", "Choose the table of the glossary that the term goes to."));
            return;
          }
          attempt(async function () {
            options.replaceChildren(make("div", "record-link-busy", "Adding “" + text + "” to " + vocabulary.name + "…"));
            const added = await api("POST", "/api/terms", draftBody({ name: text }, vocabulary, table.value, editor.person));
            await known(added["@id"], text, TERM);
          });
        });
        more.addEventListener("click", function () {
          options.replaceChildren();
          proposeTerm(text, vocabulary, function (iri, name) {
            attempt(function () { return known(iri, name, TERM); });
          });
        });
        panel.append(make("span", "record-link-label", "Table of the glossary"), table, store, more);
        if (!editor.person) {
          panel.append(make("div", "record-link-note", "No person record has your ORCID iD, so the term is stored without a contributor."));
        }
        options.append(panel);
      } else if (vocabulary[SPACE]) {
        const asked = make("div");
        options.append(asked);
        attempt(function () { return registryTerms(text, vocabulary[SPACE], new Set(), asked); });
      } else {
        registerTerm(text, vocabulary, function (iri, name) {
          attempt(function () { return known(iri, name, TERM); });
        });
      }
    }
    adding.addEventListener("click", addDirectly);

    // Search the records of the classes of the field with the text in their name, then offer a new record or term. An
    // emptied field has no link.
    // While an empty field has the focus, its earlier values are offered.
    search.addEventListener("focusin", function () {
      if (!search.value.trim()) {
        options.replaceChildren();
        heldOptions("");
      }
    });
    search.addEventListener("focusout", function () {
      window.setTimeout(function () {
        if (!search.value.trim() && !box.contains(field.getRootNode().activeElement)) {
          options.replaceChildren();
        }
      }, 200);
    });

    // List the registry terms with the text that are not on the platform.
    async function registryTerms(text, space, seen, asked) {
      const searching = make("div", "record-link-busy", "Searching the registry…");
      asked.replaceWith(searching);
      const matched = await api("GET", "/api/registries/terms?" + query({ text: text, namespace: space }));
      const fresh = matched.terms.filter(function (found) { return !seen.has(found["@id"]); });
      for (const found of fresh) {
        option([make("span", "record-link-kind text", "＋ " + matched.title), found.name + (found.code ? " · " + found.code : "")], function () {
          attempt(async function () {
            options.replaceChildren(make("div", "record-link-busy", "Registering “" + found.name + "”…"));
            const body = { "@id": found["@id"], name: found.name, termCode: found.code, inDefinedTermSet: { "@id": vocabulary["@id"] } };
            if (found.description) {
              body.description = found.description;
            }
            const added = await api("POST", "/api/terms", body);
            await known(added["@id"], found.name, TERM);
          });
        });
      }
      if (fresh.length) {
        searching.remove();
      } else {
        searching.replaceWith(make("div", "record-link-problem text-secondary", "No other terms in the registry."));
      }
    }

    search.addEventListener("keydown", function (event) {
      const asked = options.querySelector(".record-link-registry");
      if (event.key === "Enter" && asked) {
        event.preventDefault();
        asked.click();
      }
    });

    let timer = null;
    search.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        attempt(async function () {
          const text = search.value.trim();
          options.replaceChildren();
          if (!text) {
            chosen.value = "";
            show();
            chosen.dispatchEvent(new Event("change", { bubbles: true }));
            return;
          }
          const space = vocabulary ? vocabulary[SPACE] || "" : "";
          const searching = make("div", "record-link-busy", "Searching…");
          options.append(searching);
          heldOptions(text);
          const seen = new Set();
          for (const of_class of Object.keys(classes)) {
            // A term is searched in the chosen vocabulary.
            const asked = { text: text, class: of_class };
            if (of_class === TERM && vocabulary) {
              asked.vocabulary = vocabulary["@id"];
            }
            const found = await api("GET", "/api/search?" + query(asked));
            // Records of the same name, such as the Exposure steps of several case-study questions, are told apart by their address.
            const names = found["@graph"].map(function (record) { return record.name; });
            for (const record of found["@graph"]) {
              seen.add(record["@id"]);
              const content = [make("span", "record-link-kind", classes[of_class]), record.name];
              if (names.indexOf(record.name) !== names.lastIndexOf(record.name)) {
                content.push(make("small", "text-muted ms-2", new URL(record["@id"]).pathname));
              }
              option(content, function () { choose(record["@id"], record.name); });
            }
          }
          // The registry of the vocabulary is searched only on request (this option, or Enter), with one request.
          if (classes[TERM] && space) {
            option(["Search " + vocabulary.name + " in its registry for “" + text + "”"], function (event) {
              const asked = event.currentTarget;
              attempt(function () { return registryTerms(text, space, seen, asked); });
            }, "record-link-new record-link-registry");
          }
          for (const of_class of Object.keys(classes)) {
            // A term of the glossary is proposed, as its address is given in the glossary.
            if (of_class === TERM && vocabulary && vocabulary[SPACE] === GLOSSARY) {
              option(["＋ Propose “" + text + "” for " + vocabulary.name + "…"], function () {
                options.replaceChildren();
                proposeTerm(text, vocabulary, function (iri, name) {
                  attempt(function () { return known(iri, name, TERM); });
                });
              }, "record-link-new");
            } else if (of_class === TERM && vocabulary) {
              option(["＋ Register “" + text + "” as a term of " + vocabulary.name + " by hand…"], function () {
                options.replaceChildren();
                registerTerm(text, vocabulary, function (iri, name) {
                  attempt(function () { return known(iri, name, TERM); });
                });
              }, "record-link-new");
            } else if (of_class !== TERM && editor.classes[of_class]) {
              option(["＋ New " + classes[of_class].toLowerCase() + " “" + text + "”…"], function () {
                options.replaceChildren();
                addRecord(of_class, classes[of_class], text, store, function (iri, name) {
                  attempt(function () { return known(iri, name, of_class); });
                });
              }, "record-link-new");
            }
          }
          searching.remove();
        });
      }, 250);
    });
    show();
    return field;
  }
}

// The search of a link field covers all its classes, so the sh:or choice of shacl-form is made at once, unless the
// field also has another kind of value, such as an address.
const watched = new WeakSet();

function pick(within) {
  const found = within.matches && within.matches(".shacl-or-constraint") ? [within] : within.querySelectorAll(".shacl-or-constraint");
  for (const constraint of found) {
    const choice = constraint.querySelector(".editor");
    if (editor.links[constraint.dataset.path] && !editor.mixed.includes(constraint.dataset.path) && choice && choice.onchange) {
      // Made once the form is drawn.
      window.requestAnimationFrame(function () {
        choice.value = "0";
        choice.onchange();
      });
    }
  }
}

// Return the kind of value of a field from its shape.
function typeOf(instance) {
  const editors = instance.querySelectorAll(".editor, .shown");
  for (const element of editors) {
    if (element.dataset.class || (element.dataset.nodeKind || "").endsWith("#IRI")) {
      return { name: "IRI", title: "An address (IRI)" };
    }
  }
  for (const element of editors) {
    if (element.shaclDatatype) {
      return { name: element.shaclDatatype.value.split(/[#/]/).pop(), title: element.shaclDatatype.value };
    }
  }
  return null;
}

// Mark value fields, not parts, with their kind of value.
function tag(within) {
  const found = within.matches && within.matches(".property-instance") ? [within] : within.querySelectorAll(".property-instance");
  for (const instance of found) {
    if (instance.querySelector(":scope > .value-type, :scope > shacl-node")) {
      continue;
    }
    const type = typeOf(instance);
    if (type) {
      const marked = make("span", "value-type", type.name);
      marked.title = type.title;
      instance.insertBefore(marked, instance.querySelector(":scope > .remove-button-wrapper"));
    }
  }
}

function watch(form) {
  if (!form.shadowRoot || watched.has(form)) {
    return;
  }
  watched.add(form);
  pick(form.shadowRoot);
  tag(form.shadowRoot);
  new MutationObserver(function (changes) {
    for (const change of changes) {
      for (const node of change.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          pick(node);
          tag(node);
        }
      }
    }
  }).observe(form.shadowRoot, { childList: true, subtree: true });
}

document.addEventListener("ready", function (event) {
  watch(event.composedPath()[0]);
});
for (const form of document.querySelectorAll("shacl-form")) {
  watch(form);
}

// Field with the address of an image, and a button to upload the image.
class ImageAddress extends Plugin {
  createEditor(template, value) {
    const field = Text.prototype.createEditor.call(this, template, value);
    const shown = field.querySelector(".shown");
    const text = field.querySelector("input.editor");
    const pick = document.createElement("input");
    pick.type = "file";
    pick.accept = "image/png,image/jpeg,image/webp,image/gif";
    pick.hidden = true;
    const upload = document.createElement("button");
    upload.type = "button";
    upload.className = "text-edit";
    upload.textContent = "Upload image";
    upload.addEventListener("click", function () { pick.click(); });
    pick.addEventListener("change", async function () {
      const body = new FormData();
      body.append("image", pick.files[0]);
      upload.textContent = "Uploading…";
      const answer = await fetch("/api/images", { method: "POST", credentials: "same-origin", headers: { "X-Form-Token": editor.token }, body: body });
      const given = await answer.json().catch(function () { return {}; });
      upload.textContent = "Upload image";
      if (!answer.ok) {
        window.alert(given.message || "The image was not uploaded.");
        return;
      }
      shown.value = given["@id"];
      text.dataset.nodeKind = IRI;
      text.value = given["@id"];
      text.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    });
    field.append(upload, pick);
    return field;
  }
}

registerPlugin(new ImageAddress({ predicate: "https://schema.org/image" }, STYLE));
for (const predicate of Object.keys(editor.links)) {
  registerPlugin(new RecordLink({ predicate: predicate }, STYLE));
}
registerPlugin(new Text({ datatype: STRING }, STYLE));
registerPlugin(new Text({ datatype: HTML }, STYLE));
