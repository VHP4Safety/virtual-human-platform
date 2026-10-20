// The index beside the form: the record and its parts with a position, such as questions, steps and sections,
// in their order. A click on a part shows the form of that part only. A part is dragged up or down among the
// parts beside it to change their order, which sets their positions. A part with values to fix gets a dot.
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

// The record, or a part with a position: a node of the index.
function indexed(node) {
  const field = node.parentElement ? node.parentElement.closest(".property-instance") : null;
  return !field || editor.ordered.includes(field.dataset.path);
}

// The nearest node of the index above an element.
function above(element) {
  for (let node = element.parentElement ? element.parentElement.closest("shacl-node") : null; node; node = node.parentElement ? node.parentElement.closest("shacl-node") : null) {
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

// The stage of a page, as the process flow of the website shows it (stageOf in case-study.js): the stage of
// its level, or 5 when it has tools or data and no pages below it.
function stage(node, level) {
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

// The positions of the parts beside each other are set in their order: 1, 2, 3 and so on.
function renumber(parts) {
  parts.forEach(function (part, at) {
    const field = own(part, POSITION);
    const input = field && field.querySelector(".editor");
    if (input && String(input.value) !== String(at + 1)) {
      input.value = String(at + 1);
      input.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    }
  });
}

// *listener* is called with each part that is shown.
export function whenSelected(listener) {
  listeners.push(listener);
}

export function outline(givenForm, nav) {
  form = givenForm;
  const closed = new Set();

  // An entry of the index: a page with its number in the process flow, as the website shows it, then the pages
  // below it in their order, then its sections of text in their order.
  function entry(node, label, depth, number) {
    const item = make("li", "record-index-item");
    const row = make("div", "record-index-row" + (node === shown ? " active" : ""));
    const parts = partsOf(node);
    const toggle = make("button", "record-index-toggle");
    toggle.type = "button";
    if (node.parentElement.closest("shacl-node")) {
      row.append(make("span", "record-index-handle bi bi-grip-vertical", ""));
    }
    row.append(toggle);
    if (node.dataset.nodeId.startsWith("_:")) {
      row.append(make("span", "record-index-section", "§" + number));
    } else if (caseStudy) {
      const at = stage(node, depth);
      const badge = make("span", "record-index-stage stage-" + at, String(at));
      badge.title = STAGES[at - 1];
      row.append(badge);
    }
    const link = make("button", "record-index-link", label);
    link.type = "button";
    link.title = label;
    link.addEventListener("click", function () { select(node); draw(); });
    row.append(link);
    if (caseStudy && depth && !node.dataset.nodeId.startsWith("_:") && empty(node)) {
      row.classList.add("record-index-empty");
      link.title = label + " (empty: hidden on the website)";
    }
    if (node.querySelector(".property-instance.invalid")) {
      const dot = make("span", "record-index-problem");
      dot.title = "Values to check";
      row.append(dot);
    }
    item.append(row);
    const key = node.dataset.nodeId;
    if (parts.size) {
      const open = !closed.has(key);
      toggle.setAttribute("aria-expanded", String(open));
      toggle.addEventListener("click", function () {
        if (closed.has(key)) {
          closed.delete(key);
        } else {
          closed.add(key);
        }
        draw();
      });
      if (open) {
        // Pages first, as their buttons come first on the page; sections of text last.
        const fields = Array.from(parts.keys()).sort(function (one, other) { return (one === HAS_PART) - (other === HAS_PART); });
        for (const path of fields) {
          const list = parts.get(path);
          const branch = make("ul", "record-index-branch");
          list.forEach(function (part, at) {
            branch.append(entry(part, valueOf(part, NAME) || "Untitled", depth + (path === HAS_PART ? 0 : 1), at + 1));
          });
          // A part is dragged among the parts beside it; their positions follow.
          Sortable.create(branch, {
            handle: ".record-index-handle",
            animation: 150,
            onEnd: function (event) {
              if (event.oldIndex !== event.newIndex) {
                const moved = list.splice(event.oldIndex, 1)[0];
                list.splice(event.newIndex, 0, moved);
                renumber(list);
              }
            },
          });
          item.append(branch);
        }
      }
    } else {
      toggle.disabled = true;
    }
    return item;
  }

  function draw() {
    const root = form.shadowRoot && form.shadowRoot.querySelector("shacl-node");
    if (!root) {
      return;
    }
    const tree = make("ul", "record-index-tree");
    caseStudy = Boolean(own(root, QUESTIONS)) || partsOf(root).has(QUESTIONS);
    tree.append(entry(root, valueOf(root, NAME) || "This record", 0, 1));
    nav.replaceChildren(tree);
  }

  listeners.push(draw);
  let timer = null;
  form.addEventListener("ready", function () {
    select(form.shadowRoot.querySelector("shacl-node"));
  });
  form.addEventListener("change", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      // A part added in the form is shown at once.
      const added = shown && Array.from(shown.querySelectorAll("shacl-node")).find(function (node) {
        return indexed(node) && above(node) === shown && !node.dataset.seen;
      });
      for (const node of form.shadowRoot.querySelectorAll("shacl-node")) {
        node.dataset.seen = "1";
      }
      if (added && form.dataset.ready) {
        select(added);
      } else if (shown) {
        select(shown);
      }
    }, 300);
  });
  form.addEventListener("ready", function () {
    for (const node of form.shadowRoot.querySelectorAll("shacl-node")) {
      node.dataset.seen = "1";
    }
    form.dataset.ready = "1";
  });
}
