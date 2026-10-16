// Plugins of shacl-form for the record editor. The fields that link to records or to the terms of
// vocabularies (sh:class, or sh:or of classes) find them by name with the platform's search (/api/search),
// and add a new record of the class, or register a new term (and its vocabulary), through the platform's
// API, so that the field links to it at once. The fields of texts (xsd:string) give shacl-form their value
// as a literal, so that a text in HTML, such as <p>...</p>, is not read as an address.
import { Plugin, registerPlugin, findLabel, loadRDF } from "https://cdn.jsdelivr.net/npm/@ulb-darmstadt/shacl-form@3.7.3/dist/bundle.js";

const IRI = "http://www.w3.org/ns/shacl#IRI";
const LABEL = "http://www.w3.org/2000/01/rdf-schema#label";
const TERM = "https://schema.org/DefinedTerm";
const STRING = "http://www.w3.org/2001/XMLSchema#string";
const editor = JSON.parse(document.getElementById("editor").textContent);

// The form is in a shadow root, which the page's styles do not reach. The inputs that show a value which
// shacl-form reads from a hidden input are as wide as its own (.editor).
const STYLE = `
.shown:not([type='checkbox']) { flex-grow: 1; }
textarea.shown { resize: vertical; }
.record-link-box > .shown { width: 100%; }
.record-link-options { display: flex; flex-direction: column; border: 1px solid #ccc; border-top: 0; max-height: 14em; overflow-y: auto; }
.record-link-options:empty { display: none; }
.record-link-options button { text-align: left; background: #fff; border: 0; border-bottom: 1px solid #eee; padding: 4px 8px; font: inherit; cursor: pointer; }
.record-link-options button:hover { background: #f1f0f7; }
.record-link-box { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.record-link-vocabulary { margin-bottom: 4px; font: inherit; }
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

// A text in the form in which shacl-form reads a literal: in quotes, as it is.
function literal(text) {
  return '"' + text + '"';
}

// The field of a text as the form's theme makes it, whose value is given to shacl-form as a literal.
class Text extends Plugin {
  createEditor(template, value) {
    const field = template.config.theme.createTextEditor(template.label, value || null, false, template);
    const shown = field.querySelector(".editor");
    shown.classList.replace("editor", "shown");
    const text = document.createElement("input");
    text.type = "hidden";
    text.className = "editor";
    text.value = shown.value ? literal(shown.value) : "";
    field.append(text);
    shown.addEventListener("input", function () {
      text.value = shown.value ? literal(shown.value) : "";
    });
    return field;
  }
}

function query(fields) {
  return Object.entries(fields).map(function (entry) { return entry[0] + "=" + encodeURIComponent(entry[1]); }).join("&");
}

class RecordLink extends Plugin {
  createEditor(template, value) {
    const of_class = template.class ? template.class.value : "";
    const named = of_class.split(/[/#]/).pop();
    const store = template.config.store;
    // The field as the form's theme makes it, with its label; its text input finds by name.
    const field = template.config.theme.createTextEditor(template.label, null, false, template);
    const search = field.querySelector(".editor");
    search.classList.replace("editor", "shown");
    search.pattern = undefined;
    search.setAttribute("placeholder", "Find a " + named + " by name");
    search.value = value ? findLabel(store.getQuads(value.value, null, null, null), template.config.languages) || value.value : "";
    // The link itself, which shacl-form reads as the field's value. A text that the record has where a link
    // belongs is kept as a text until a record is chosen.
    const chosen = document.createElement("input");
    chosen.type = "hidden";
    chosen.className = "editor";
    if (value && value.termType === "Literal") {
      chosen.value = literal(value.value);
      search.value = value.value;
    } else {
      chosen.dataset.nodeKind = IRI;
      chosen.value = value ? value.value : "";
    }
    const options = document.createElement("div");
    options.className = "record-link-options";
    // The search takes the place of the field's input, with the matches under it; the link stays a child of
    // the field, where shacl-form reads the field's values.
    const box = document.createElement("div");
    box.className = "record-link-box";
    search.replaceWith(box);
    box.append(search, options);
    field.append(chosen);

    function choose(iri, name) {
      chosen.dataset.nodeKind = IRI;
      chosen.value = iri;
      search.value = name;
      options.replaceChildren();
      chosen.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function option(text, onClick) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = text;
      button.addEventListener("click", onClick);
      options.append(button);
    }

    // A record or a term that is added is put in the form's graph too, so that the form's checks know it.
    async function known(iri, name) {
      store.addQuads(await loadRDF({ rdf: "<" + iri + "> a <" + of_class + "> ; <" + LABEL + "> " + JSON.stringify(name) + " ." }));
      choose(iri, name);
    }

    async function attempt(action) {
      try {
        await action();
      } catch (error) {
        options.replaceChildren();
        option(error.message, function () {});
      }
    }

    // A field of terms first chooses the vocabulary, in whose namespace the terms are found.
    let vocabulary = null;
    if (of_class === TERM) {
      const vocabularies = document.createElement("select");
      vocabularies.className = "record-link-vocabulary";
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

    let timer = null;
    search.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        attempt(async function () {
          const text = search.value.trim();
          options.replaceChildren();
          if (!text) {
            return;
          }
          const within = vocabulary && vocabulary.url ? vocabulary.url["@id"] : "";
          const found = await api("GET", "/api/search?" + query({ text: text, class: of_class, within: within }));
          for (const record of found["@graph"]) {
            option(record.name, function () { choose(record["@id"], record.name); });
          }
          if (of_class === TERM && vocabulary) {
            option("Register a term of " + vocabulary.name + ": " + text, function () {
              const iri = window.prompt("The address of the term " + text, within);
              if (iri) {
                attempt(async function () {
                  const added = await api("POST", "/api/terms", { "@id": iri, name: text, inDefinedTermSet: { "@id": vocabulary["@id"] } });
                  await known(added["@id"], text);
                });
              }
            });
          } else if (editor.classes[of_class]) {
            option("New " + named + ": " + text, function () {
              attempt(async function () {
                const added = await api("POST", "/api/" + editor.classes[of_class], { name: text });
                await known(added["@id"], text);
              });
            });
          }
        });
      }, 250);
    });
    return field;
  }
}

for (const predicate of editor.links) {
  registerPlugin(new RecordLink({ predicate: predicate }, STYLE));
}
registerPlugin(new Text({ datatype: STRING }, STYLE));
