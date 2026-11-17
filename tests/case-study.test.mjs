// Check of the case study drawn by static/js/case-study.js: the stage of a page, and the placement of the pages of a
// question in the grid of its overview.
// Run with: node tests/case-study.test.mjs
import assert from "node:assert/strict";
import * as caseStudy from "../static/js/case-study.js";

function step(id, name, more) {
  return Object.assign({ "@id": id, name: name }, more);
}

// A use of a tool, method or dataset: of a record at an address, or given as a text.
function use(name, address) {
  return { name: name, item: address ? { "@id": address } : name };
}

const question = step("q", "Question 1", { text: "What is asked?", step: [
  // A greyed-out page is not opened, also if it has pages with content.
  step("q/a", "Hazard", { position: 1, creativeWorkStatus: "Incomplete", step: [step("q/a/x", "Not opened", { tool: [use("T")] })] }),
  // A page with one page of the same name below it.
  step("q/b", "Kinetics", { position: 2, step: [step("q/b/k", "Modelling", { step: [step("q/b/k/k", "Modelling", {
    tool: [use("PBK", "https://x.org/tools/pbk"), use("Assay", "https://x.org/methods/assay")], supply: [use("Data"), use("Set", "https://x.org/data/d1")] })] })] }),
  // A page with items and pages below it: a page at level 5, a page without content and a page given by its address.
  step("q/c", "Dynamics", { position: 3, tool: [use("Own")], step: [
    step("q/c/d", "Deep", { position: 1, step: [step("q/c/d/d", "Deeper", { step: [step("q/c/d/d/d", "Deepest", { supply: [use("Measured")] })] })] }),
    step("q/c/e", "Empty", { position: 2, step: [step("q/c/e/e", "Empty too", {})] }),
    { "@id": "q/c/h" },
  ] }),
  { name: "No address", position: 4, tool: [use("T")] },
  // A page with content only in a page below it, which is given by its address, as in the preview of the editor.
  step("q/f", "Flat", { position: 5, step: [{ "@id": "q/f/x" }] }),
  step("q/o", "Outcome", { position: 6, text: "A text." }),
] });
const nodes = new Map([
  ["q/c/h", step("q/c/h", "By address", { position: 3, tool: [use("R")] })],
  ["q/f/x", step("q/f/x", "Sub", { tool: [use("S")] })],
]);

// Return the cells of a layout as lines: the name, the first row + the rows, the first column - the last column.
function cells(found) {
  const lines = [];
  (function walk(pages) {
    for (const node of pages) {
      lines.push(node.name + " " + node.row + "+" + node.rows + " " + node.column + "-" + node.last);
      walk(node.below);
    }
  })(found.pages);
  return lines;
}

function find(found, name) {
  let wanted = null;
  (function walk(pages) {
    for (const node of pages) {
      wanted = wanted || (node.name === name ? node : null);
      walk(node.below);
    }
  })(found.pages);
  return wanted;
}

function names(node) {
  return node.items.map(function (kind) { return kind.map(function (item) { return item.name; }); });
}

// A step given by its address has content, so the page above it is not at the stage of its tools.
assert.equal(caseStudy.stageOf({ tool: [use("Own")], step: [{ "@id": "q/f/x" }] }, 2, nodes), 3);

// On the website.
const site = caseStudy.layout({ options: {}, nodes: nodes }, question);
assert.deepEqual([site.columns, site.rows], [4, 7]);
assert.deepEqual(cells(site), [
  "Hazard 0+1 1-7",
  "Kinetics 1+1 1-1", "Modelling 1+1 2-4",
  "Dynamics 2+3 1-1", "Deep 3+1 2-2", "Deeper 3+1 3-3", "Deepest 3+1 4-4", "By address 4+1 2-4",
  "Flat 5+1 1-1", "Sub 5+1 2-4",
  "Outcome 6+1 1-4",
]);
assert.equal(find(site, "Hazard").greyed, true);
assert.equal(find(site, "Hazard").items, null);
assert.deepEqual(find(site, "Hazard").below, []);
// The page of the same name is opened, and its tools, methods and data have a column each.
assert.deepEqual(find(site, "Modelling").path, ["q", "q/b", "q/b/k", "q/b/k/k"]);
assert.deepEqual(names(find(site, "Modelling")), [["PBK"], ["Assay"], ["Data", "Set"]]);
assert.deepEqual(names(find(site, "Dynamics")), [["Own"], [], []]);
assert.deepEqual(names(find(site, "Deepest")), [[], [], ["Measured"]]);
assert.deepEqual(names(find(site, "Outcome")), [[], [], []]);
assert.equal(find(site, "Kinetics").items, null);
assert.equal(find(site, "Flat").faded, false);

// The methods of a dataset that is read are in the row of the dataset, after the methods of the page, each once. A
// dataset that is not read yet adds none.
const methods = [{ name: "Assay", address: "https://x.org/methods/assay" }, { name: "Other assay", address: "https://x.org/methods/other" }];
const read = caseStudy.layout({ options: {}, nodes: nodes, datasets: new Map([["https://x.org/data/d1", { address: "https://x.org/data/d1", methods: methods }]]) }, question);
assert.deepEqual(names(find(read, "Modelling")), [["PBK"], ["Assay", "Other assay"], ["Data", "Set"]]);
assert.deepEqual(find(read, "Modelling").items[1][1].from, ["https://x.org/data/d1"]);
assert.deepEqual(cells(read), cells(site));
const unread = caseStudy.layout({ options: {}, nodes: nodes, datasets: new Map([["https://x.org/data/d1", null]]) }, question);
assert.deepEqual(names(find(unread, "Modelling")), [["PBK"], ["Assay"], ["Data", "Set"]]);

// In the preview of the editor, the pages without content are shown, and a greyed-out page is still not opened.
const preview = caseStudy.layout({ options: { openDisabled: true }, nodes: nodes }, question);
assert.deepEqual([preview.columns, preview.rows], [4, 8]);
assert.deepEqual(cells(preview).slice(7), [
  "Empty 4+1 2-2", "Empty too 4+1 3-4", "By address 5+1 2-4",
  "Flat 6+1 1-1", "Sub 6+1 2-4",
  "Outcome 7+1 1-4",
]);
assert.equal(find(preview, "Empty").faded, true);
assert.equal(find(preview, "Empty too").faded, true);
assert.deepEqual(find(preview, "Hazard").below, []);

console.log("The case study is drawn as expected.");
