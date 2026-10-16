// shacl-form plugins of the record editor. Link fields (sh:class, or sh:or of classes) show the kind of what
// they link to and find records by name (/api/search); missing records are added in a dialog, and terms are
// registered with their vocabulary. Text fields give shacl-form literals, so HTML is not read as an address.
import { Plugin, registerPlugin, findLabel, loadRDF } from "https://cdn.jsdelivr.net/npm/@ulb-darmstadt/shacl-form@3.7.3/dist/bundle.js";
import { busy } from "./busy.js";

const IRI = "http://www.w3.org/ns/shacl#IRI";
const LABEL = "http://www.w3.org/2000/01/rdf-schema#label";
const TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const TARGET = "http://www.w3.org/ns/shacl#targetClass";
const NAME = "https://schema.org/name";
const TERM = "https://schema.org/DefinedTerm";
const STRING = "http://www.w3.org/2001/XMLSchema#string";
const HTML = "http://www.w3.org/1999/02/22-rdf-syntax-ns#HTML";
const editor = JSON.parse(document.getElementById("editor").textContent);

// The form's shadow root is not reached by the page's styles. Shown inputs are as wide as .editor ones.
const STYLE = `
.shown:not([type='checkbox']) { flex-grow: 1; }
textarea.shown { resize: vertical; }
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
    throw new Error(answer.message || response.statusText);
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

// Platform addresses are opened on this server, so they work on every copy.
function local(iri) {
  return iri.startsWith(editor.base) ? "/" + iri.slice(editor.base.length) : iri;
}

// A text as shacl-form reads a literal: quoted, with its datatype unless plain (such as rdf:HTML).
function literal(text, datatype) {
  return '"' + text + '"' + (datatype && datatype !== STRING ? "^^" + datatype : "");
}

function query(fields) {
  return Object.entries(fields).map(function (entry) { return entry[0] + "=" + encodeURIComponent(entry[1]); }).join("&");
}

// A text field of the theme, given to shacl-form as a literal of the field's datatype. An address where a
// text belongs is kept until the text is edited.
class Text extends Plugin {
  createEditor(template, value) {
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
    return field;
  }
}

// A dialog with a title, a place for refusals and a body; it is removed when closed.
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

// A new record, in a dialog form made from its class's shape; once added, it is given to *added*.
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
  // Adding is decided by the platform's checks, as in the editor's form.
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
        throw new Error(answer.message || response.statusText);
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

// A vocabulary added from a registry (OLS, Ontobee, Wikidata), found by name, or given by hand. One the
// platform has at the same namespace is chosen instead.
async function addVocabulary(platform, added) {
  const shown = opened("Add a vocabulary");
  const registry = make("select", "form-select form-select-sm");
  for (const [name, title] of Object.entries(await api("GET", "/api/registries"))) {
    registry.append(new Option(title, name));
  }
  registry.append(new Option("By hand", ""));
  const text = make("input", "form-control form-control-sm");
  text.placeholder = "Name, such as assay or BAO";
  const results = make("div", "list-group list-group-flush border rounded small record-dialog-results");
  const name = make("input", "form-control form-control-sm");
  name.placeholder = "Name, such as NCBI Taxonomy";
  const namespace = make("input", "form-control form-control-sm");
  namespace.placeholder = "Term address start, such as http://purl.obolibrary.org/obo/NCBITaxon_";
  const add = make("button", "btn btn-success btn-sm mt-2", "Add the vocabulary");
  add.type = "button";
  const finding = make("div", "");
  finding.append(labelled("Name", text), results);
  const writing = make("div", "d-none");
  writing.append(labelled("Name", name), labelled("Namespace", namespace), add);
  shown.body.append(labelled("Registry", registry), finding, writing);

  async function keep(found, button) {
    for (const vocabulary of platform) {
      if (vocabulary.url && vocabulary.url["@id"] === found.namespace) {
        shown.dialog.close();
        added(vocabulary["@id"]);
        return;
      }
    }
    const working = busy(button, "Adding…", shown.body);
    try {
      const body = { name: found.title, url: { "@id": found.namespace } };
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

  let timer = null;
  let asked = 0;
  async function find() {
    finding.classList.toggle("d-none", !registry.value);
    writing.classList.toggle("d-none", Boolean(registry.value));
    results.replaceChildren();
    if (!registry.value) {
      return;
    }
    // Only the latest answer is shown.
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
  registry.addEventListener("change", find);
  text.addEventListener("input", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(find, 300);
  });
  add.addEventListener("click", function () {
    keep({ title: name.value.trim(), namespace: namespace.value.trim() }, add);
  });
  find();
}

// A term registered by hand, with label and address, in a platform vocabulary.
function registerTerm(text, vocabulary, added) {
  const shown = opened("Register a term of " + vocabulary.name);
  const label = make("input", "form-control form-control-sm");
  label.value = text;
  const address = make("input", "form-control form-control-sm");
  address.value = vocabulary.url ? vocabulary.url["@id"] : "";
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

class RecordLink extends Plugin {
  createEditor(template, value) {
    // The field's link classes by name, from the profile; text fields, such as tool keywords, have none.
    const classes = template.class || template.or ? editor.links[template.path] || {} : {};
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
    // The link, read by shacl-form as the value. A text where a link belongs is kept until a record is chosen.
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
    const options = make("div", "record-link-options");
    const row = make("div", "record-link-row");
    const box = make("div", "record-link-box");
    search.replaceWith(box);
    row.append(kind, search, open);
    box.append(row, options);
    field.append(chosen);

    // The linked record's kind and page. Texts, records of other classes and unknown addresses are marked.
    function show() {
      kind.className = "record-link-kind";
      kind.textContent = "";
      kind.title = "";
      open.hidden = true;
      if (!chosen.value) {
        return;
      }
      if (chosen.dataset.nodeKind !== IRI) {
        kind.classList.add("text");
        kind.textContent = "Text";
        kind.title = "Name only: find or add its record";
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
      chosen.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function option(content, onClick, className) {
      const button = make("button", className || "");
      button.type = "button";
      button.append(...content);
      button.addEventListener("click", onClick);
      // Options are listed above the search that is still running.
      options.insertBefore(button, options.querySelector(".record-link-busy"));
    }

    // Added records and terms are put in the form's graph too, for the form's checks.
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

    // Term fields choose a vocabulary first; terms are found in its namespace.
    let vocabulary = null;
    if (classes[TERM]) {
      const vocabularies = make("select", "record-link-vocabulary");
      box.prepend(vocabularies);
      let listed = [];
      const fill = async function (selected) {
        listed = (await api("GET", "/api/vocabularies?page_size=200"))["@graph"];
        vocabularies.replaceChildren();
        for (const found of listed) {
          vocabularies.append(new Option(found.name, found["@id"], false, found["@id"] === selected));
        }
        vocabularies.append(new Option("Add a vocabulary…", ""));
        // A held term is shown in the vocabulary whose namespace starts its address; a field of one
        // vocabulary (sh:pattern ^<namespace>) shows only that one.
        const only = template.pattern && template.pattern.startsWith("^") ? template.pattern.slice(1).replace(/\\(.)/g, "$1") : "";
        const current = listed.find(function (found) {
          return found.url && ((only && found.url["@id"] === only) || (value && value.value.startsWith(found.url["@id"])));
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
      };
      vocabularies.addEventListener("change", function () {
        vocabulary = listed.find(function (found) { return found["@id"] === vocabularies.value; }) || null;
        if (vocabularies.value) {
          return;
        }
        attempt(function () {
          return addVocabulary(listed, function (iri) { attempt(function () { return fill(iri); }); });
        });
      });
      attempt(function () { return fill(null); });
    }

    // Records of the field's classes whose name has the text, then a new record or term. An emptied field
    // links to nothing.
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
          const within = vocabulary && vocabulary.url ? vocabulary.url["@id"] : "";
          const searching = make("div", "record-link-busy", "Searching…");
          options.append(searching);
          const seen = new Set();
          for (const of_class of Object.keys(classes)) {
            const found = await api("GET", "/api/search?" + query({ text: text, class: of_class, within: within }));
            for (const record of found["@graph"]) {
              seen.add(record["@id"]);
              option([make("span", "record-link-kind", classes[of_class]), record.name], function () { choose(record["@id"], record.name); });
            }
          }
          // Registry terms not on the platform yet; registered with label, definition and code when chosen.
          if (classes[TERM] && within) {
            const matched = await api("GET", "/api/registries/terms?" + query({ text: text, namespace: within }));
            for (const found of matched.terms) {
              if (seen.has(found["@id"])) {
                continue;
              }
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
          }
          for (const of_class of Object.keys(classes)) {
            if (of_class === TERM && vocabulary) {
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

// A link field searches all its classes, so shacl-form's sh:or choice is made at once.
const watched = new WeakSet();

function pick(within) {
  const found = within.matches && within.matches(".shacl-or-constraint") ? [within] : within.querySelectorAll(".shacl-or-constraint");
  for (const constraint of found) {
    const choice = constraint.querySelector(".editor");
    if (editor.links[constraint.dataset.path] && choice && choice.onchange) {
      // Made once the form has drawn it.
      window.requestAnimationFrame(function () {
        choice.value = "0";
        choice.onchange();
      });
    }
  }
}

// A field's value kind from its shape: IRI (sh:class, sh:nodeKind sh:IRI), else its sh:datatype.
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

// Value fields, not parts, are marked with their value kind.
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

for (const predicate of Object.keys(editor.links)) {
  registerPlugin(new RecordLink({ predicate: predicate }, STYLE));
}
registerPlugin(new Text({ datatype: STRING }, STYLE));
registerPlugin(new Text({ datatype: HTML }, STYLE));
