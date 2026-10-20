// The index beside the form shows one page at a time, as the website does: the way down to the page, the page
// with its number in the process flow, the pages below it and its sections of text. A click on a page or a
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
rokit-collapsible.shacl-group:not(.focus-chrome) { display: block; margin: 0 0 1rem; border: 1px solid #d9d4ec; border-left: 4px solid #29235c; border-radius: 6px; background: #fff; }
rokit-collapsible.shacl-group:not(.focus-chrome)::part(header) { font-weight: 600; color: #29235c; background: #f3f1f9; border-radius: 0 6px 0 0; }
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
  if (!steps && (filled(node, TOOL) || filled(node, SUPPLY))) {
    return 5;
  }
  return Math.min(level + 1, 4);
}

let form = null;
let shown = null;
let caseStudy = false;
const listeners = [];

// Only the fields of *target* are shown. The fields of the parts in the index below it are hidden; they are
// reached through the index.
export function select(target) {
  const root = form.shadowRoot.querySelector("shacl-node");
  if (!root || !target) {
    return;
  }
  if (!form.shadowRoot.getElementById("focus-style")) {
    const style = make("style");
    style.id = "focus-style";
    style.textContent = STYLE;
    form.shadowRoot.append(style);
  }
  shown = target;
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
  // Parts with a position are added and ordered in the index, so their own cards are left out of the form.
  for (const path of Object.keys(editor.ordered)) {
    const button = addButton(target, path);
    const card = button ? button.closest("rokit-collapsible") : null;
    if (card) {
      card.classList.add("focus-hidden");
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

// The add button of the form for a field of a node, found by the label of the field.
function addButton(node, path) {
  const names = editor.ordered[path] || [];
  for (const button of node.querySelectorAll(".add-button-wrapper rokit-button.add-button")) {
    if (button.closest("shacl-node") === node && names.includes(button.textContent.trim())) {
      return button;
    }
  }
  return null;
}

export function outline(givenForm, nav) {
  form = givenForm;
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

  // A list of parts of the page that can be dragged, with a button to add one at its end.
  function list(title, page, path, parts, add) {
    const box = make("section", "record-index-list");
    const head = make("div", "record-index-list-head");
    head.append(make("span", "", title));
    const native = addButton(page, path);
    const button = make("button", "btn btn-sm btn-outline-vhppurple py-0", "+ " + add);
    button.type = "button";
    button.disabled = !native;
    button.addEventListener("click", function () {
      adding = { page: page, path: path };
      native.click();
      window.setTimeout(added, 400);
    });
    head.append(button);
    box.append(head);
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
      if (!section && caseStudy && empty(part)) {
        row.classList.add("record-index-empty");
        link.title = name + " (empty: hidden on the website)";
      }
      dot(part, row);
      const count = (partsOf(part).get(HAS_PART) || []).length + pagesBelow(part).length;
      const into = make("span", "record-index-into", count ? count + " ›" : "›");
      into.title = count ? count + " pages and sections inside" : "Nothing inside yet";
      row.append(into);
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
    return box;
  }

  function draw() {
    const root = form.shadowRoot && form.shadowRoot.querySelector("shacl-node");
    if (!root) {
      return;
    }
    caseStudy = Boolean(own(root, QUESTIONS)) || Boolean(addButton(root, QUESTIONS));
    const page = shown || root;
    const view = make("div", "record-index-view");
    // The way down to the page; a click goes up.
    const trail = way(page);
    if (trail.length > 1) {
      const crumbs = make("nav", "record-index-crumbs");
      trail.slice(0, -1).forEach(function (node) {
        const up = make("button", "record-index-crumb", (isSection(node) ? "§ " : "") + (valueOf(node, NAME) || "Untitled"));
        up.type = "button";
        up.addEventListener("click", function () { select(node); draw(); });
        crumbs.append(up, make("span", "record-index-crumb-gap", "›"));
      });
      view.append(crumbs);
    }
    // The page itself; a click shows its own form.
    const card = make("button", "record-index-page" + (shown === page ? " active" : ""));
    card.type = "button";
    card.title = "Edit this page";
    const section = isSection(page);
    if (section) {
      card.append(make("span", "record-index-section", "§"));
    } else if (caseStudy) {
      card.append(badge(page));
    }
    const words = make("span", "record-index-page-words");
    words.append(make("span", "record-index-page-name", valueOf(page, NAME) || "Untitled"));
    if (section) {
      words.append(make("span", "record-index-page-stage", "Section of text"));
    } else if (caseStudy) {
      words.append(make("span", "record-index-page-stage", STAGES[stage(page) - 1]));
    }
    card.append(words);
    dot(page, card);
    card.addEventListener("click", function () { select(page); draw(); });
    view.append(card);
    // Its pages below, then its sections of text, as the website shows them.
    const parts = partsOf(page);
    for (const path of Object.keys(editor.ordered)) {
      if (path === HAS_PART || !(parts.has(path) || addButton(page, path))) {
        continue;
      }
      const question = path === QUESTIONS;
      view.append(list(question ? "Questions" : "Pages below", page, path, parts.get(path) || [], question ? "Add question" : "Add step"));
    }
    if (parts.has(HAS_PART) || addButton(page, HAS_PART)) {
      view.append(list(section ? "Subsections" : "Sections of text", page, HAS_PART, parts.get(HAS_PART) || [], section ? "Add subsection" : "Add section"));
    }
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
    adding = null;
    for (const node of form.shadowRoot.querySelectorAll("shacl-node")) {
      node.dataset.seen = "1";
    }
    place(found, list.length);
    select(found);
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
