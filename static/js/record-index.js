// The index beside the form of a case study shows one page at a time, as the website does: the way down to the
// page, the page with its number in the process flow, the pages below it and its sections of text. A click on a page or a
// section below goes down to it and shows its form only; a section shows its subsections. A click on the way
// goes up.
// Pages and sections are dragged up or down to change their order, which sets their positions, and they are
// added at the end of their list. A part with values to check gets a dot.
import Sortable from "https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/modular/sortable.esm.js";

const NAME = "https://schema.org/name";
const POSITION = "https://schema.org/position";
const HAS_PART = "https://schema.org/hasPart";
const TOOL = "https://schema.org/tool";
const SUPPLY = "https://schema.org/supply";
const QUESTIONS = "https://vhp4safety.github.io/glossary#VHP0000151";
// The fields of a case study page that are used at one level only, by that level: the heading of a question page,
// and the process flow step of a step of a question. At other levels they are left out of the form.
const ONE_LEVEL = { "https://schema.org/headline": 1, "https://schema.org/additionalType": 2 };
// The fields of a section that are used on the pages of the site only: its figures after the text (images go in the
// text of a case study), the record it presents, the fields of that record it shows, and its address elsewhere.
const SITE_ONLY = ["https://schema.org/image", "https://schema.org/about", "https://platform.vhp4safety.nl/model/v1/form#shows", "https://schema.org/url"];
// The colours of the stages, as the case study pages give them.
const COLOURS = ["--bs-vhppink-distinct", "--bs-vhpdarkpurple", "--bs-vhpdarkteal", "--bs-vhplightteal", "--bs-vhpblue"];
// The stages of the process flow, as the case study pages name them.
const STAGES = ["Regulatory Question", "Safety Assessment Workflow Step", "Case Study Step", "Case Study Substep", "Tools, Models and Data"];
// The fields that give a step something to show; a step without them, and without such steps, is empty.
const CONTENT = [TOOL, SUPPLY, "https://bioschemas.org/terms/input", "https://bioschemas.org/terms/output", HAS_PART, "https://schema.org/text", "https://schema.org/description"];
const editor = JSON.parse(document.getElementById("editor").textContent);

// The form is drawn in a shadow root, which the page styles do not reach. The groups of a form are cards. While
// a part is shown, the other parts and fields are hidden, and the groups around it lose their headers.
const STYLE = `
.focus-hidden { display: none !important; }
.focus-chrome { padding: 0 !important; margin: 0 !important; border: 0 !important; background: none !important; box-shadow: none !important; }
rokit-collapsible.focus-chrome::part(header) { display: none; }
.property-instance.focus-chrome > .remove-button-wrapper { display: none; }
.focus-chrome > rokit-button.add-button, .focus-chrome > .add-button-wrapper { display: none; }
.property-instance.focus-parts { display: none; }
shacl-property:has(> .property-instance[data-path="${POSITION}"]) { display: none; }
rokit-collapsible.shacl-group:not(.focus-chrome) { display: block; margin: 0 0 1rem; border: 1px solid #d9d4ec; border-left: 4px solid var(--stage, #29235c); border-radius: 6px; background: #fff; }
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
rokit-collapsible.shacl-group:not(.focus-chrome)::part(header) { font-weight: 600; color: var(--stage, #29235c); background: color-mix(in srgb, var(--stage, #29235c) 7%, white); border-radius: 0 6px 0 0; }
`;

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className || "";
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// The field of a node with the path, not a field of one of its parts.
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

// The record, or a part with a position: a node of the index.
function indexed(node) {
  const field = node.parentElement ? node.parentElement.closest(".property-instance") : null;
  return !field || field.dataset.path in editor.ordered;
}

function isSection(node) {
  return node.dataset.nodeId.startsWith("_:");
}

// The nearest node of the index above an element.
function above(element) {
  for (let node = parentNode(element); node; node = parentNode(node)) {
    if (indexed(node)) {
      return node;
    }
  }
  return null;
}

// The parts of a node in the index, by field, in order of position.
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

// Whether the field of a node has a value or a part.
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

// The pages below a node: its questions or steps, not its sections of text.
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

// The way from the record down to a page: the record, then each page in between.
function way(page) {
  const found = [];
  for (let node = page; node; node = above(node)) {
    found.unshift(node);
  }
  return found;
}

// The stage of a page, as the process flow of the website shows it (stageOf in case-study.js): the stage of
// its level, or 5 when it has tools or data and no pages below it.
function stage(node) {
  const level = way(node).length - 1;
  const steps = pagesBelow(node).some(function (step) { return !empty(step); });
  if (!steps && (filled(node, TOOL) || filled(node, SUPPLY) || node.dataset.intended === "5")) {
    return 5;
  }
  return Math.min(level + 1, 4);
}

let form = null;
let shown = null;
// The list of the parts of a field, as the index draws it; set by outline().
let partsList = null;
// Only a case study is edited a page at a time, with the index and the colours of its stages; other records are
// edited in one form.
const caseStudy = editor.caseStudy;
const listeners = [];

// Only the fields of *target* are shown. The fields of the parts in the index below it are hidden; they are
// reached through the index.
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
  // The cards of the form take the colour of the stage of the page being edited, or of the page of a section.
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
  // The card of a field of parts with a position, such as the questions of a case study, lists them as the index
  // does: a click opens one, they are dragged to order them, and they are added at the end.
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

// A part of the form is shown with its node, and its first field takes the focus.
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

// The part shown in the form.
export function current() {
  return shown;
}

// *listener* is called with each part that is shown.
export function whenSelected(listener) {
  listeners.push(listener);
}

// The position of a part is set, when the part has a position field.
function place(part, at) {
  const field = own(part, POSITION);
  const input = field && field.querySelector(".editor");
  if (input && String(input.value) !== String(at)) {
    input.value = String(at);
    input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
  }
}

// The field of a node with the path, as shacl-form draws it (shacl-property), also when it has no value.
function property(node, path) {
  for (const found of node.querySelectorAll("shacl-property")) {
    if (found.template && found.template.path === path && found.closest("shacl-node") === node) {
      return found;
    }
  }
  return null;
}

// The add button of the form for a field of a node.
function addButton(node, path) {
  const field = property(node, path);
  return field ? field.querySelector(".add-button-wrapper rokit-button.add-button") : null;
}

export function outline(givenForm, nav) {
  form = givenForm;
  if (!caseStudy || !nav) {
    return;
  }
  // The field a part is added to; once the form has drawn the new part, it is placed last and shown.
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

  // A list of parts of the page that can be dragged and removed, with buttons to add one at its end. Each button
  // says what it adds; for a case study, the number in the process flow of the page it adds.
  function list(title, page, path, parts, adds) {
    const box = make("section", "record-index-list");
    box.append(make("div", "record-index-list-head", title));
    const items = make("ol", "record-index-items");
    const section = path === HAS_PART;
    parts.forEach(function (part, at) {
      const row = make("li", "record-index-row" + (part === shown ? " active" : ""));
      row.append(make("span", "record-index-handle bi bi-grip-vertical", ""));
      row.append(section ? make("span", "record-index-section", "§" + (at + 1)) : caseStudy ? badge(part) : make("span", "record-index-section", String(at + 1)));
      const name = valueOf(part, NAME) || "Untitled";
      const link = make("button", "record-index-link", name);
      link.type = "button";
      link.title = section ? "Edit this section" : "Open this page";
      link.addEventListener("click", function () { select(part); draw(); });
      row.append(link);
      if (!section && caseStudy && empty(part) && part.dataset.intended !== "5") {
        row.classList.add("record-index-empty");
        link.title = name + " (empty: hidden on the website)";
      }
      dot(part, row);
      const inside = (partsOf(part).get(HAS_PART) || []).length + pagesBelow(part).length;
      const into = make("span", "record-index-into", inside ? inside + " ›" : "›");
      into.title = inside ? inside + " pages and sections inside" : "Nothing inside yet";
      row.append(into);
      const remove = make("button", "record-index-remove bi bi-trash", "");
      remove.type = "button";
      remove.title = "Remove";
      remove.addEventListener("click", function () {
        const more = inside ? " The " + inside + " pages and sections inside it are removed too." : "";
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
    // A part is dragged among the parts beside it; their positions follow, 1, 2, 3 and so on.
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

  // The add buttons of a field of a page: what they add, with the number of its stage for a case study.
  function addsFor(page, field) {
    if (field === HAS_PART) {
      return [{ text: isSection(page) ? "§ Subsection" : "§ Text section" }];
    }
    if (caseStudy && field === QUESTIONS) {
      return [{ stage: 2, text: "Regulatory question" }];
    }
    if (caseStudy) {
      // A page below is a page of steps (the next stage, at most 4), or a page of tools, models and data (5).
      const next = Math.min(way(page).length + 1, 4);
      return [{ stage: next, text: STAGES[next - 1] + " page" }, { stage: 5, text: STAGES[4] + " page" }];
    }
    return [{ text: "Add " + ((editor.ordered[field] || [])[0] || "part").toLowerCase() }];
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
    // The pages above, from the record down to the page being edited, each one level further in; a click goes
    // back to that page.
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
    // Its pages below, then its sections of text, as the website shows them.
    const parts = partsOf(page);
    for (const field of Object.keys(editor.ordered)) {
      if (field === HAS_PART || !(parts.has(field) || addButton(page, field))) {
        continue;
      }
      below.append(list(field === QUESTIONS ? "Questions" : "Pages below", page, field, parts.get(field) || [], addsFor(page, field)));
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
  // The part that was added is the one not seen before; it goes last in its list and is shown.
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
