// Requests of new terms for the VHP4Safety glossary.
export const GLOSSARY = "https://vhp4safety.github.io/glossary#";
// The tables of the terms in the glossary repository (templates/<table>.tsv), as in the field Table of the glossary
// of the Term profile (term:glossaryTable). Chemicals are left out, as they have Wikibase items in place of glossary
// addresses.
export const TABLES = ["toxicology", "risk_assessment", "adverse_outcome", "process_flow", "tools", "server", "projects", "organizations"];
// The field of the table and the field of the contributors of a term, by their JSON names.
export const TABLE_FIELD = "term:glossaryTable";
export const CONTRIBUTOR_FIELD = "dct:contributor";
const FORM = "https://github.com/VHP4Safety/glossary/issues/new";

// Return a choice of the table for a new term. A draft term of the glossary needs a table, so no table is chosen
// until the editor chooses one.
export function tableChoice(selected) {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  select.required = true;
  select.append(new Option("Choose a table…", "", false, !selected));
  for (const table of TABLES) {
    select.append(new Option(table.replaceAll("_", " "), table, false, table === selected));
  }
  return select;
}

// Return the body of a new draft term of the glossary, in table, with the signed-in editor as its contributor.
export function draftBody(term, vocabulary, table, person) {
  const body = { name: term.name, inDefinedTermSet: { "@id": vocabulary["@id"] }, creativeWorkStatus: "Draft" };
  body[TABLE_FIELD] = table;
  if (person) {
    body[CONTRIBUTOR_FIELD] = [{ "@id": person }];
  }
  if (term.abbreviation) {
    body.alternateName = term.abbreviation;
  }
  if (term.definition) {
    body.description = term.definition;
  }
  if (term.references && term.references.length) {
    body["http://www.w3.org/2000/01/rdf-schema#isDefinedBy"] = term.references.map(function (given) { return { "@id": given }; });
  }
  return body;
}

// Return the address of the term request form, filled in with a term and its table.
export function requestAddress(term, table) {
  const context = ["Table: templates/" + table + ".tsv"];
  if (term.references && term.references.length) {
    context.push("References: " + term.references.join(", "));
  }
  if (term.address) {
    context.push("Draft term on the VHP4Safety platform: " + term.address);
  }
  const fields = {
    template: "ontology-term-request.yml",
    title: "[TERM REQUEST] " + term.name,
    label: term.name,
    definition: term.definition || "",
    acronym: term.abbreviation || "",
    context: context.join("\n"),
  };
  return FORM + "?" + new URLSearchParams(fields).toString();
}

// Open the request form in a new tab.
export function openRequest(term, table) {
  window.open(requestAddress(term, table), "_blank", "noopener");
}
