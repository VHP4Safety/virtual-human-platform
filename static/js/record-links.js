// Plugins of shacl-form for the record editor. A field that links to records or to the terms of vocabularies
// (sh:class, or sh:or of classes) shows what it links to and of which kind, and finds the records of its
// classes by name with the platform's search (/api/search). A record that is not on the platform yet is added
// in a form of its own, made from the shape of its class, in a dialog; a term is registered with its
// vocabulary. Both are added through the platform's API, and the field links to them at once. The fields of
// texts (xsd:string) give shacl-form their value as a literal, so that a text in HTML, such as <p>...</p>, is
// not read as an address.
import { Plugin, registerPlugin, findLabel, loadRDF } from "https://cdn.jsdelivr.net/npm/@ulb-darmstadt/shacl-form@3.7.3/dist/bundle.js";

const IRI = "http://www.w3.org/ns/shacl#IRI";
const LABEL = "http://www.w3.org/2000/01/rdf-schema#label";
const TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const TARGET = "http://www.w3.org/ns/shacl#targetClass";
const NAME = "https://schema.org/name";
const TERM = "https://schema.org/DefinedTerm";
const STRING = "http://www.w3.org/2001/XMLSchema#string";
const HTML = "http://www.w3.org/1999/02/22-rdf-syntax-ns#HTML";
const editor = JSON.parse(document.getElementById("editor").textContent);

// The form is in a shadow root, which the page's styles do not reach. The inputs that show a value which
// shacl-form reads from a hidden input are as wide as its own (.editor).
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

// A platform address is opened from this server, so that it works on every copy of the platform.
function local(iri) {
  return iri.startsWith(editor.base) ? "/" + iri.slice(editor.base.length) : iri;
}

// A text in the form in which shacl-form reads a literal: in quotes, as it is, with its datatype when it is
// not a plain text, such as HTML (rdf:HTML).
function literal(text, datatype) {
  return '"' + text + '"' + (datatype && datatype !== STRING ? "^^" + datatype : "");
}

function query(fields) {
  return Object.entries(fields).map(function (entry) { return entry[0] + "=" + encodeURIComponent(entry[1]); }).join("&");
}

// The field of a text as the form's theme makes it, whose value is given to shacl-form as a literal of the
// field's datatype, a plain text or HTML. An address that a record has where a text belongs is kept as an
// address until the text is edited.
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

// A new record of a class, in a form of its own made from the shape of the class, in a dialog. It is added
// through the API, and then given to *added* with its address and name.
function addRecord(of_class, label, name, store, added) {
  const shape = store.getSubjects(TARGET, of_class, null)[0];
  const subject = "urn:uuid:" + crypto.randomUUID();
  const dialog = make("dialog", "record-dialog");
  const top = make("div", "d-flex align-items-center gap-2 border-bottom px-3 py-2");
  const close = make("button", "btn-close");
  close.type = "button";
  close.setAttribute("aria-label", "Close");
  close.addEventListener("click", function () { dialog.close(); });
  top.append(make("h2", "h5 mb-0 me-auto", "New " + label.toLowerCase()), close);
  const refused = make("div", "alert alert-danger small mx-3 mt-3 mb-0 d-none");
  const form = document.createElement("shacl-form");
  form.dataset.shapesUrl = document.querySelector("shacl-form").dataset.shapesUrl;
  form.dataset.shapeSubject = shape ? shape.value : "";
  form.dataset.valuesSubject = subject;
  form.dataset.values = "<" + subject + "> a <" + of_class + "> ; <" + NAME + "> " + JSON.stringify(name) + " .";
  form.dataset.generateNodeShapeReference = "";
  form.dataset.collapse = "open";
  // The platform's checks decide whether the record is added, as in the editor's own form.
  const add = make("button", "btn btn-success", "Add the " + label.toLowerCase());
  add.type = "button";
  add.addEventListener("click", async function () {
    const response = await fetch("/api/" + editor.classes[of_class], {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Form-Token": editor.token, "Content-Type": "text/turtle", Accept: "application/json" },
      body: form.serialize("text/turtle"),
    });
    const answer = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      refused.textContent = answer.message || response.statusText;
      refused.classList.remove("d-none");
      return;
    }
    const record = await api("GET", "/api" + local(answer["@id"]));
    dialog.close();
    added(answer["@id"], record.name || name);
  });
  const body = make("div", "p-3");
  const bar = make("div", "editor-save mt-3");
  bar.append(add);
  body.append(form, bar);
  dialog.append(top, refused, body);
  dialog.addEventListener("close", function () { dialog.remove(); });
  document.body.append(dialog);
  dialog.showModal();
}

class RecordLink extends Plugin {
  createEditor(template, value) {
    // The classes of the records that the field links to, by their name, as the profile gives them; a field
    // of texts whose property links to records elsewhere, such as the keywords of a tool, has none.
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
    open.title = "Open its page";
    // The link itself, which shacl-form reads as the field's value. A text that the record has where a link
    // belongs is kept as a text until a record is chosen.
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

    // What the field links to: the kind of the record, and a link to its page. A text where a link belongs,
    // a record of another class, and an address that is no record of the platform are marked.
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
        kind.title = "A name only: find its record, or add it";
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
        kind.title = named ? "A record of another kind than the field's" : "An address that is no record of the platform";
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
      options.append(button);
    }

    // A record or a term that is added is put in the form's graph too, so that the form's checks know it.
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

    // A field of terms first chooses the vocabulary, in whose namespace the terms are found.
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
        vocabularies.append(new Option("Another vocabulary…", ""));
        // A term that the field has already is shown in its vocabulary, the one whose namespace starts its
        // address; a field whose terms are of one vocabulary (sh:pattern ^<namespace>) shows that one only.
        const only = template.pattern && template.pattern.startsWith("^") ? template.pattern.slice(1).replace(/\\(.)/g, "$1") : "";
        const current = listed.find(function (found) {
          return found.url && ((only && found.url["@id"] === only) || (value && value.value.startsWith(found.url["@id"])));
        });
        if (current && !selected) {
          vocabularies.value = current["@id"];
        } else if (value && !selected) {
          vocabularies.prepend(new Option("Not in a vocabulary of the platform", "none", true, true));
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
        const name = window.prompt("The name of the vocabulary, such as NCBI Taxonomy");
        const namespace = name && window.prompt("The start of the addresses of its terms, such as http://purl.obolibrary.org/obo/NCBITaxon_");
        if (namespace) {
          attempt(async function () {
            const added = await api("POST", "/api/vocabularies", { name: name, url: { "@id": namespace } });
            await fill(added["@id"]);
          });
        }
      });
      attempt(function () { return fill(null); });
    }

    // The records of each of the field's classes whose name has the text, then a new record of each class
    // that has a kind, or a new term of the vocabulary. A field whose text is emptied links to nothing.
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
          for (const of_class of Object.keys(classes)) {
            const found = await api("GET", "/api/search?" + query({ text: text, class: of_class, within: within }));
            for (const record of found["@graph"]) {
              option([make("span", "record-link-kind", classes[of_class]), record.name], function () { choose(record["@id"], record.name); });
            }
          }
          for (const of_class of Object.keys(classes)) {
            if (of_class === TERM && vocabulary) {
              option(["＋ Register “" + text + "” as a term of " + vocabulary.name], function () {
                const iri = window.prompt("The address of the term " + text, within);
                if (iri) {
                  attempt(async function () {
                    const added = await api("POST", "/api/terms", { "@id": iri, name: text, inDefinedTermSet: { "@id": vocabulary["@id"] } });
                    await known(added["@id"], text, TERM);
                  });
                }
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
        });
      }, 250);
    });
    show();
    return field;
  }
}

// A field of links is one search for the records of any of its classes, so the choice among the classes of
// sh:or, which shacl-form asks for first when a value is added, is made at once.
const watched = new WeakSet();

function pick(within) {
  const found = within.matches && within.matches(".shacl-or-constraint") ? [within] : within.querySelectorAll(".shacl-or-constraint");
  for (const constraint of found) {
    const choice = constraint.querySelector(".editor");
    if (editor.links[constraint.dataset.path] && choice && choice.onchange) {
      // The choice is made once the form has drawn it.
      window.requestAnimationFrame(function () {
        choice.value = "0";
        choice.onchange();
      });
    }
  }
}

// The kind of value of a field, as its shape gives it: an address (IRI), when the field links to a class or
// takes addresses (sh:class, sh:nodeKind sh:IRI), or else the datatype of its literals (sh:datatype).
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

// Each field that holds values, not parts, is marked with the kind of its values.
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
