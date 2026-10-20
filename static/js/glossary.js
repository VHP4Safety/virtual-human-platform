// Requests of new terms for the VHP4Safety glossary.
export const GLOSSARY = "https://vhp4safety.github.io/glossary#";
// The tables of the terms in the glossary repository (templates/<table>.tsv). Chemicals are left out, as they have
// Wikibase items in place of glossary addresses.
const TABLES = ["toxicology", "risk_assessment", "adverse_outcome", "process_flow", "tools", "server", "projects", "organizations"];
const FORM = "https://github.com/VHP4Safety/glossary/issues/new";

// Return a choice of the table for a new term.
export function tableChoice() {
  const select = document.createElement("select");
  select.className = "form-select form-select-sm";
  for (const table of TABLES) {
    select.append(new Option(table.replace("_", " "), table));
  }
  return select;
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

// Open the request form in a new tab, within a few seconds of the click.
export function openRequest(term, table) {
  window.open(requestAddress(term, table), "_blank", "noopener");
}
