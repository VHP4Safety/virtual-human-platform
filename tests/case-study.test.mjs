// Check of the case study drawn by static/js/case-study.js.
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

const nodes = new Map([
  ["q/f/x", step("q/f/x", "Sub", { tool: [use("S")] })],
]);

// A step given by its address has content, so the page above it is not at the stage of its tools.
assert.equal(caseStudy.stageOf({ tool: [use("Own")], step: [{ "@id": "q/f/x" }] }, 2, nodes), 3);

console.log("The case study is drawn as expected.");
