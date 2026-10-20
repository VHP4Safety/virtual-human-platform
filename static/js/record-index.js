// Index of the pages and sections of a case study, next to the form. One page is shown at a time, as on the website:
// the way down to the page, the page with its number in the process flow, the pages below it and its sections of
// text. A click on a page or a section below opens its form only, and a section is shown with its subsections. A click
// on the way goes up.
// Pages and sections are dragged up or down to change their order, which sets their positions. New parts are added at
// the end of their list. A part with values to check is marked with a dot.
import Sortable from "https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/modular/sortable.esm.js";

const NAME = "https://schema.org/name";
const POSITION = "https://schema.org/position";
const HAS_PART = "https://schema.org/hasPart";
const TOOL = "https://schema.org/tool";
const SUPPLY = "https://schema.org/supply";
const STEP = "https://schema.org/step";
const QUESTIONS = "https://vhp4safety.github.io/glossary#VHP0000151";
// The fields with pages of the process flow. Tools and data are items of a page, not pages.
const PAGES = [QUESTIONS, STEP];
// The fields of a case study page that are used at one level only, by that level: the heading of a question page,
// and the process flow step of a step of a question. At other levels they are left out of the form.
const ONE_LEVEL = { "https://schema.org/headline": 1, "https://schema.org/additionalType": 2 };
// The fields of a section that are used on the pages of the site only: its figures after the text (images go in the
// text of a case study), the presented record, the shown fields of that record, and its address elsewhere.
const SITE_ONLY = ["https://schema.org/image", "https://schema.org/about", "https://platform.vhp4safety.nl/model/v1/form#shows", "https://schema.org/url"];
// The colours of the stages, as on the case study pages.
const COLOURS = ["--bs-vhppink-distinct", "--bs-vhpdarkpurple", "--bs-vhpdarkteal", "--bs-vhplightteal", "--bs-vhpblue"];
// The names of the stages of the process flow, as on the case study pages.
const STAGES = ["Regulatory Question", "Safety Assessment Workflow Step", "Case Study Step", "Case Study Substep", "Tools, Models and Data"];
// The fields with content for a step. A step without these fields, and without steps with them, is empty.
const CONTENT = [TOOL, SUPPLY, "https://bioschemas.org/terms/input", "https://bioschemas.org/terms/output", HAS_PART, "https://schema.org/text", "https://schema.org/description"];
const editor = JSON.parse(document.getElementById("editor").textContent);

// The style of the form. The form is drawn in a shadow root, so the page styles are not applied to it. The groups of
// a form are cards. While a part is shown, the other parts and fields are hidden, and the headers of the groups around
// it are removed.
const STYLE = `
.focus-hidden { display: none !important; }
.focus-chrome { padding: 0 !important; margin: 0 !important; border: 0 !important; background: none !important; box-shadow: none !important; }
rokit-collapsible.focus-chrome::part(header) { display: none; }
.property-instance.focus-chrome > .remove-button-wrapper { display: none; }
.focus-chrome > rokit-button.add-button, .focus-chrome > .add-button-wrapper { display: none; }
.property-instance.focus-parts { display: none; }
shacl-property:has(> .property-instance[data-path="${POSITION}"]) { display: none; }
rokit-collapsible.shacl-group:not(.focus-chrome) { display: block; margin: 0 0 1rem; border: 1px solid #d9d4ec; border-radius: 6px; background: #fff; }
.focus-list { display: block; box-sizing: border-box; width: 100%; padding: 0.25rem 0.75rem 0.75rem; font-size: 0.95em; text-align: left; }
.focus-list ol { margin: 0; padding: 0; list-style: none; }
.focus-list .record-index-list-head { display: none; }
.focus-list .record-index-row { display: flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.35rem; border-radius: 4px; }
.focus-list .record-index-row:hover { background: #f3f1f9; }
.focus-list .record-index-link { flex: 1; border: 0; background: none; text-align: left; color: #212529; cursor: pointer; font: inherit; }
.focus-list .record-index-handle { cursor: grab; color: #9a95b8; }
.focus-list .record-index-stage { display: inline-flex; align-items: center; justify-content: center; width: 1.3rem; height: 1.3rem; border-radius: 50%; color: #fff; font-size: 0.75rem; font-weight: 700; }
.focus-list .stage-1 { background: var(--bs-vhppink-distinct); } .focus-list .stage-2 { background: var(--bs-vhpdarkpurple); }
.focus-list .stage-3 { background: var(--bs-vhpdarkteal); } .focus-list .stage-4 { background: var(--bs-vhplightteal); } .focus-list .stage-5 { background: var(--bs-vhpblue); }
.focus-list .record-index-section, .focus-list .record-index-into, .focus-list .record-index-none { color: #6c6891; font-size: 0.85em; }
.focus-list .record-index-remove { border: 0; background: none; color: #6c6891; visibility: hidden; cursor: pointer; }
.focus-list .record-index-row:hover .record-index-remove { visibility: visible; }
.focus-list .record-index-problem { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: #dc3545; }
.focus-list .record-index-adds { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.4rem; }
.focus-list .record-index-adds button { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.1rem 0.5rem; border: 1px solid #29235c; border-radius: 4px; background: #fff; color: #29235c; font: inherit; font-size: 0.85em; cursor: pointer; }
.focus-list .record-index-adds button:hover { background: #29235c; color: #fff; }
rokit-collapsible.shacl-group:not(.focus-chrome)::part(header) { font-weight: 600; color: var(--stage, #29235c); background: color-mix(in srgb, var(--stage, #29235c) 7%, white); border-radius: 6px 6px 0 0; }
`;

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className || "";
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// Return the field of a node with the path, not a field of one of its parts.
function own(node, path) {
  for (const field of node.querySelectorAll('.property-instance[data-path="' + path + '"]')) {
    if (field.closest("shacl-node") === node) {
      return field;
    }
  }
  return null;
}

function valueOf(node, path) {
  const field = own(node, path);
  const input = field && (field.querySelector(".shown") || field.querySelector(".editor"));
  return input ? String(input.value || "").trim() : "";
}

function position(node) {
  const found = parseFloat(valueOf(node, POSITION));
  return isNaN(found) ? Infinity : found;
}

function parentNode(node) {
  return node.parentElement ? node.parentElement.closest("shacl-node") : null;
}

// Return true for a node of the index: the record, or a part with a position.
function indexed(node) {
  const field = node.parentElement ? node.parentElement.closest(".property-instance") : null;
  return !field || field.dataset.path in editor.ordered;
}

// A part of a record: a node without an address, or a part address under its record (<record>#<field>-<n>).
const PART = /#[A-Za-z_][A-Za-z0-9_]*-[0-9]+$/;

export function isPart(id) {
  return id.startsWith("_:") || PART.test(id);
}

function isSection(node) {
  return isPart(node.dataset.nodeId);
}

// Return the nearest node of the index above an element.
function above(element) {
  for (let node = parentNode(element); node; node = parentNode(node)) {
    if (indexed(node)) {
      return node;
    }
  }
  return null;
}

// Return the parts of a node in the index, by field, in order of position.
function partsOf(node) {
  const found = new Map();
  for (const part of node.querySelectorAll("shacl-node")) {
    if (indexed(part) && above(part) === node) {
      const path = part.parentElement.closest(".property-instance").dataset.path;
      if (!found.has(path)) {
        found.set(path, []);
      }
      found.get(path).push(part);
    }
  }
  for (const list of found.values()) {
    list.sort(function (one, other) { return position(one) - position(other); });
  }
  return found;
}

// Return true if the field of a node has a value or a part.
function filled(node, path) {
  for (const field of node.querySelectorAll('.property-instance[data-path="' + path + '"]')) {
    if (field.closest("shacl-node") !== node) {
      continue;
    }
    const input = field.querySelector(".shown") || field.querySelector(".editor");
    if (field.querySelector("shacl-node") || (input && String(input.value || "").trim())) {
      return true;
    }
  }
  return false;
}

// Return the pages below a node: its questions or steps, not its sections of text.
function pagesBelow(node) {
  const found = [];
  for (const [path, list] of partsOf(node)) {
    if (path !== HAS_PART) {
      found.push(...list);
    }
  }
  return found;
}

function empty(node) {
  return !CONTENT.some(function (path) { return filled(node, path); }) && pagesBelow(node).every(empty);
}

// Return the way from the record down to a page: the record, then each page in between.
function way(page) {
  const found = [];
  for (let node = page; node; node = above(node)) {
    found.unshift(node);
  }
  return found;
}

// Return the stage of a page, as in the process flow of the website (stageOf in case-study.js): the stage of its
// level, or 5 if it has tools or data and no pages below it.
function stage(node) {
  const level = way(node).length - 1;
  const parts = partsOf(node);
  const steps = PAGES.some(function (path) { return (parts.get(path) || []).some(function (step) { return !empty(step); }); });
  if (!steps && (filled(node, TOOL) || filled(node, SUPPLY) || node.dataset.intended === "5")) {
    return 5;
  }
  return Math.min(level + 1, 4);
}

let form = null;
let shown = null;
// The function that draws the list of the parts of a field, as in the index; set by outline().
let partsList = null;
// Only a case study is edited a page at a time, with the index and the colours of its stages; other records are
// edited in one form.
const caseStudy = editor.caseStudy;
const listeners = [];

// Show only the fields of *target*. Hide the fields of the parts in the index below it; they are opened through the
// index.
export function select(target) {
  const root = form.shadowRoot.querySelector("shacl-node");
  if (!root || !target || !caseStudy) {
    return;
  }
  if (!form.shadowRoot.getElementById("focus-style")) {
    const style = make("style");
    style.id = "focus-style";
    style.textContent = STYLE;
    form.shadowRoot.append(style);
  }
  shown = target;
  // Give the cards of the form the colour of the stage of the edited page, or of the page of a section.
  let page = target;
  while (isSection(page) && above(page)) {
    page = above(page);
  }
  document.documentElement.style.setProperty("--stage", "var(" + COLOURS[stage(page) - 1] + ")");
  for (const element of root.querySelectorAll("rokit-collapsible, shacl-property, .property-instance, shacl-node")) {
    const around = element !== target && element.contains(target);
    const inside = target.contains(element) && element !== target;
    let ownField = false;
    if (inside) {
      const part = element.tagName === "SHACL-NODE" && indexed(element) ? element : above(element);
      ownField = part === target;
    }
    const holdsPart = element.matches(".property-instance") && ownField && Array.from(element.children).some(function (child) {
      return child.tagName === "SHACL-NODE" && indexed(child);
    });
    element.classList.toggle("focus-chrome", around);
    element.classList.toggle("focus-parts", holdsPart);
    element.classList.toggle("focus-hidden", !around && element !== target && !ownField);
  }
  root.classList.toggle("focus-chrome", root !== target);
  if (caseStudy) {
    const level = way(target).length - 1;
    const hidden = isSection(target) ? SITE_ONLY : Object.keys(ONE_LEVEL).filter(function (path) { return ONE_LEVEL[path] !== level; });
    for (const path of hidden) {
      const field = property(target, path);
      if (field) {
        field.classList.add("focus-hidden");
      }
    }
  }
  // List the parts with a position in the card of their field, such as the questions of a case study, as in the
  // index: a click opens a part, parts are dragged to change their order, and new parts are added at the end.
  for (const path of Object.keys(editor.ordered)) {
    const field = property(target, path);
    const card = field ? field.querySelector("rokit-collapsible") : null;
    if (card && partsList) {
      for (const old of card.querySelectorAll(":scope > .focus-list")) {
        old.remove();
      }
      const wrapper = card.querySelector(":scope > .add-button-wrapper");
      if (wrapper) {
        wrapper.classList.add("focus-hidden");
      }
      const listed = partsList(target, path);
      listed.classList.add("focus-list");
      card.append(listed);
    }
  }
  for (const listener of listeners) {
    listener(target);
  }
}

// Show a part of the form with its node, and focus its first field.
export function reveal(target) {
  const node = target.tagName === "SHACL-NODE" && indexed(target) ? target : above(target);
  select(node || target);
  window.requestAnimationFrame(function () {
    target.scrollIntoView({ block: "center", behavior: "smooth" });
    const first = target.matches(".property-instance") ? target.querySelector(".shown, .editor:not([type=hidden])")
      : target.querySelector(".property-instance .shown, .property-instance .editor:not([type=hidden])");
    if (first) {
      first.focus({ preventScroll: true });
    }
  });
}

// Return the part that is shown in the form.
export function current() {
  return shown;
}

// Call *listener* with each part that is shown.
export function whenSelected(listener) {
  listeners.push(listener);
}

// Set the position of a part, if the part has a position field.
function place(part, at) {
  const field = own(part, POSITION);
  const input = field && field.querySelector(".editor");
  if (input && String(input.value) !== String(at)) {
    input.value = String(at);
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  }
}

// Return the field of a node with the path, as drawn by shacl-form (shacl-property), also if it has no value.
function property(node, path) {
  for (const found of node.querySelectorAll("shacl-property")) {
    if (found.template && found.template.path === path && found.closest("shacl-node") === node) {
      return found;
    }
  }
  return null;
}

// Return the add button of the form for a field of a node.
function addButton(node, path) {
  const field = property(node, path);
  return field ? field.querySelector(".add-button-wrapper rokit-button.add-button") : null;
}

export function outline(givenForm, nav) {
  form = givenForm;
  if (!caseStudy || !nav) {
    return;
  }
  // The field to which a part is added. When the new part is drawn in the form, it is placed last and shown.
  let adding = null;

  function badge(node) {
    const at = stage(node);
    const found = make("span", "record-index-stage stage-" + at, String(at));
    found.title = STAGES[at - 1];
    return found;
  }

  function dot(node, row) {
    if (node.querySelector(".property-instance.invalid")) {
      const found = make("span", "record-index-problem");
      found.title = "Values to check";
      row.append(found);
    }
  }

  // Return a list of parts of the page that can be dragged and removed, with buttons to add a part at the end. The
  // text of a button names the kind of part, and for a case study the number of its stage in the process flow.
  function list(title, page, path, parts, adds) {
    const box = make("section", "record-index-list");
    box.append(make("div", "record-index-list-head", title));
    const items = make("ol", "record-index-items");
    const section = path === HAS_PART;
    const pageList = caseStudy && PAGES.includes(path);
    parts.forEach(function (part, at) {
      const row = make("li", "record-index-row" + (part === shown ? " active" : ""));
      row.append(make("span", "record-index-handle bi bi-grip-vertical", ""));
      row.append(section ? make("span", "record-index-section", "§" + (at + 1)) : pageList ? badge(part) : make("span", "record-index-section", String(at + 1)));
      const name = valueOf(part, NAME) || "Untitled";
      const link = make("button", "record-index-link", name);
      link.type = "button";
      link.title = section ? "Edit this section" : "Open this page";
      link.addEventListener("click", function () { select(part); draw(); });
      row.append(link);
      if (pageList && empty(part) && part.dataset.intended !== "5") {
        row.classList.add("record-index-empty");
        link.title = name + " (empty: hidden on the website)";
      }
      dot(part, row);
      const inside = (partsOf(part).get(HAS_PART) || []).length + pagesBelow(part).length;
      const into = make("span", "record-index-into", inside ? inside + " ›" : "›");
      into.title = inside ? inside + " parts inside" : "Nothing inside yet";
      row.append(into);
      const remove = make("button", "record-index-remove bi bi-trash", "");
      remove.type = "button";
      remove.title = "Remove";
      remove.addEventListener("click", function () {
        const more = inside ? " The " + inside + " parts inside it are removed too." : "";
        if (!window.confirm("Remove “" + name + "”?" + more + " Nothing is removed from the platform until Save.")) {
          return;
        }
        const field = part.parentElement.closest(".property-instance");
        const button = field ? field.querySelector(":scope > .remove-button-wrapper rokit-button.remove-button") : null;
        if (button) {
          button.click();
        }
        window.setTimeout(function () { select(page); draw(); }, 300);
      });
      row.append(remove);
      items.append(row);
    });
    if (!parts.length) {
      items.append(make("li", "record-index-none", "None yet."));
    }
    // A part is dragged among the parts next to it, and the positions are set again: 1, 2, 3 and so on.
    Sortable.create(items, {
      handle: ".record-index-handle",
      draggable: ".record-index-row",
      animation: 150,
      onEnd: function (event) {
        if (event.oldIndex !== event.newIndex) {
          const moved = parts.splice(event.oldIndex, 1)[0];
          parts.splice(event.newIndex, 0, moved);
          parts.forEach(function (part, at) { place(part, at + 1); });
        }
      },
    });
    box.append(items);
    const native = addButton(page, path);
    const buttons = make("div", "record-index-adds");
    for (const add of adds) {
      const button = make("button", "btn btn-sm btn-outline-vhppurple");
      button.type = "button";
      button.append(document.createTextNode("+ "));
      if (add.stage) {
        button.append(make("span", "record-index-stage stage-" + add.stage, String(add.stage)));
      }
      button.append(document.createTextNode(add.text));
      button.disabled = !native;
      button.addEventListener("click", function () {
        adding = { page: page, path: path, stage: add.stage };
        native.click();
        window.setTimeout(added, 400);
      });
      buttons.append(button);
    }
    box.append(buttons);
    return box;
  }

  // Return the add buttons of a field of a page: the kind of part, with the number of its stage for a case study.
  function addsFor(page, field) {
    if (field === HAS_PART) {
      return [{ text: isSection(page) ? "§ Subsection" : "§ Text section" }];
    }
    if (caseStudy && field === QUESTIONS) {
      return [{ stage: 2, text: "Regulatory question" }];
    }
    if (caseStudy && PAGES.includes(field)) {
      // A page below is a page of steps (the next stage, at most 4), or a page of tools, models and data (5).
      const next = Math.min(way(page).length + 1, 4);
      return [{ stage: next, text: STAGES[next - 1] + " page" }, { stage: 5, text: STAGES[4] + " page" }];
    }
    return [{ text: (editor.ordered[field] || [])[0] || "Part" }];
  }

  partsList = function (page, field) {
    return list("", page, field, partsOf(page).get(field) || [], addsFor(page, field));
  };

  function draw() {
    const root = form.shadowRoot && form.shadowRoot.querySelector("shacl-node");
    if (!root) {
      return;
    }
    const page = shown || root;
    const view = make("div", "record-index-view");
    // The pages above, from the record down to the edited page, each indented one more level. A click opens that page
    // again.
    const trail = way(page);
    const path = make("ol", "record-index-path");
    const section = isSection(page);
    trail.forEach(function (node, depth) {
      const row = make("li", "record-index-row" + (node === page ? " active" : ""));
      row.style.paddingLeft = depth * 0.85 + "rem";
      if (isSection(node)) {
        row.append(make("span", "record-index-section", "§"));
      } else if (caseStudy) {
        row.append(badge(node));
      }
      const link = make("button", "record-index-link", valueOf(node, NAME) || "Untitled");
      link.type = "button";
      link.title = node === page ? "Edit this page" : "Go back to this page";
      link.addEventListener("click", function () { select(node); draw(); });
      row.append(link);
      dot(node, row);
      if (node === page) {
        row.append(make("span", "record-index-editing", "editing"));
      }
      path.append(row);
    });
    view.append(path);
    const below = make("div", "record-index-below");
    below.style.marginLeft = (trail.length - 1) * 0.85 + 1.3 + "rem";
    // The pages below, then the sections of text, as on the website.
    const parts = partsOf(page);
    // The lists are in the order of the fields in the form.
    const order = Array.from(page.querySelectorAll("shacl-property")).filter(function (found) {
      return found.closest("shacl-node") === page;
    }).map(function (found) { return found.template ? found.template.path : ""; });
    const fields = Object.keys(editor.ordered).sort(function (one, other) { return order.indexOf(one) - order.indexOf(other); });
    for (const field of fields) {
      if (field === HAS_PART || !(parts.has(field) || addButton(page, field))) {
        continue;
      }
      const title = field === QUESTIONS ? "Questions" : field === STEP ? "Pages below" : (editor.ordered[field] || [])[0] || "";
      below.append(list(title, page, field, parts.get(field) || [], addsFor(page, field)));
    }
    if (parts.has(HAS_PART) || addButton(page, HAS_PART)) {
      below.append(list(section ? "Subsections" : "Sections of text", page, HAS_PART, parts.get(HAS_PART) || [], addsFor(page, HAS_PART)));
    }
    view.append(below);
    nav.replaceChildren(view);
  }

  listeners.push(draw);
  let timer = null;
  form.addEventListener("ready", function () {
    for (const node of form.shadowRoot.querySelectorAll("shacl-node")) {
      node.dataset.seen = "1";
    }
    select(form.shadowRoot.querySelector("shacl-node"));
  });
  // Return the added part: the part not seen before. Place it last in its list and show it.
  function added() {
    if (!adding) {
      return false;
    }
    const list = partsOf(adding.page).get(adding.path) || [];
    const found = list.find(function (part) { return !part.dataset.seen; });
    if (!found) {
      return false;
    }
    for (const node of form.shadowRoot.querySelectorAll("shacl-node")) {
      node.dataset.seen = "1";
    }
    if (adding.stage === 5) {
      found.dataset.intended = "5";
    }
    adding = null;
    place(found, list.length);
    select(found);
    if (found.dataset.intended === "5") {
      const card = Array.from(found.querySelectorAll("rokit-collapsible")).find(function (collapsible) {
        return collapsible.closest("shacl-node") === found && /tool/i.test(collapsible.label || "");
      });
      if (card) {
        card.open = true;
        card.scrollIntoView({ block: "start", behavior: "smooth" });
      }
    }
    return true;
  }

  form.addEventListener("change", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      if (!added()) {
        select(shown || form.shadowRoot.querySelector("shacl-node"));
      }
    }, 300);
  });
}
