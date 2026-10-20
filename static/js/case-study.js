// A case study is drawn here from its JSON-LD document, as the website shows it. The document comes from
// GET /api/casestudies/<case>, or from the editor preview of unsaved changes. One page is shown at a time.
// The case study page shows the questions. A question page shows the process flow steps, and each step page
// shows the steps below it. Each page has a heading, a summary, buttons and text in sections. The buttons
// open the pages one level down, and the tools, methods and data. Empty steps are not shown on the website.
// Buttons, breadcrumbs and the process flow navigate in place. A container that is drawn again with a new
// document stays on its page.
//
//   import { renderCaseStudy, stageOf } from "/static/js/case-study.js";
//   renderCaseStudy(container, caseStudy, options);
//
// Options, all optional:
//   base         the platform's base address; platform links are made on this server, so they work on
//                every copy of the platform
//   at           the address of the page to show; without it, the container stays on its page
//   linkTarget   where links open, such as "_blank" in the editor
//   openDisabled true opens the pages that are greyed out on the website, and shows empty steps greyed, so
//                that they can be previewed
//   onNavigate   called with the address of the page in view, after a click opens another
//   onPick       called with the page in view, the field, the section ({position, name}) and the value of
//                what is clicked, such as the text of a section. Links are then not opened by a click. A
//                button to a page opens that page, and onPick is called for the opened page. An icon beside
//                each tool, method and data button opens the link in a new tab.
//
// markField(container, address, field, section) marks what shows a field of a page, such as the one an
// editor's form is on, and opens that page.
//
// stageOf(page, level) gives the stage of a page in the process flow, from 1 to 5.

// Heading colours by level: case study, question, process flow step, its steps, and deeper steps.
const HEADINGS = ["text-vhppink-distinct", "text-vhpdarkpurple", "text-vhpdarkteal", "text-vhplightteal", "text-vhpblue", "text-vhplightteal"];
// Colours of the buttons to the pages one level down: questions, process flow steps, steps, sub-steps.
// Tools, methods and data are blue.
const BUTTONS = ["btn-vhppink-distinct", "btn-vhpdarkpurple", "btn-vhpdarkteal", "btn-vhplightteal"];
const ITEMS = "btn-vhpblue";
const PROCESS_FLOW = ["Regulatory Question", "Safety Assessment Workflow Step", "Case Study Step", "Case Study Substep", "Tools, Models and Data"];
// The fields that give a step content to show.
const CONTENT = ["tool", "supply", "bioschemas:input", "bioschemas:output", "hasPart", "text", "description"];
// Elements left out of a text, as they run code or change the page around it.
const UNSAFE = "script, style, iframe, frame, frameset, object, embed, link, meta, base, form";
// The deepest level searched; only steps that hold their own page go deeper.
const DEEPEST = 20;

// Each container's state: the document, the path to the page in view, the open sections and the marked field.
const states = new WeakMap();
let containers = 0;

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className || "";
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// A field's values: one is given as itself, several as a list.
function all(node, name) {
  const given = node ? node[name] : undefined;
  if (given === undefined || given === null) {
    return [];
  }
  return Array.isArray(given) ? given : [given];
}

// A field's first value as a text: a typed value's value ({"@value": "1"}), or a link's address.
function first(node, name) {
  const value = all(node, name)[0];
  if (value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    if (value["@value"] !== undefined) {
      return String(value["@value"]);
    }
    return value["@id"] || "";
  }
  return String(value);
}

// A document's nodes by address, so a node given by address only ({"@id": ...}) is found where it is held:
// at its first link only, such as a tool that two steps use.
function index(node, found) {
  if (Array.isArray(node)) {
    for (const item of node) {
      index(item, found);
    }
  } else if (node && typeof node === "object") {
    const known = found.get(node["@id"]);
    if (node["@id"] && Object.keys(node).length > 1 && (!known || (!known.name && node.name))) {
      found.set(node["@id"], node);
    }
    for (const name of Object.keys(node)) {
      if (name !== "@context") {
        index(node[name], found);
      }
    }
  }
  return found;
}

function number(node) {
  const position = parseFloat(first(node, "position"));
  return isNaN(position) ? Infinity : position;
}

// Pages, sections and items are ordered by position, then by name.
function byPosition(one, other) {
  if (number(one) !== number(other)) {
    return number(one) < number(other) ? -1 : 1;
  }
  return first(one, "name").localeCompare(first(other, "name"), undefined, { numeric: true });
}

// The nodes of a page's field, such as steps or sections, in order.
function parts(state, page, name) {
  const found = [];
  for (const value of all(page, name)) {
    if (value && typeof value === "object") {
      found.push(state.nodes.get(value["@id"]) || value);
    }
  }
  found.sort(byPosition);
  return found;
}

// A page's label on its button: the name of the kind of step it is, a vocabulary term, without the term's
// own kind in brackets ("Exposure" for "Exposure (Process Flow Step)"), else its own name.
function label(state, node) {
  for (const value of all(node, "additionalType")) {
    const term = value && typeof value === "object" ? state.nodes.get(value["@id"]) || value : null;
    const name = term ? first(term, "name") : "";
    if (name) {
      return name.replace(/\s*\([^)]*\)$/, "");
    }
  }
  return first(node, "name");
}

// The pages one level down: the case study's questions, or a page's steps.
function children(state, page, level) {
  return parts(state, page, level === 0 ? "regulatoryQuestion" : "step");
}

// A step is empty when it has no content and no steps with content.
function empty(step) {
  for (const name of CONTENT) {
    if (all(step, name).length) {
      return false;
    }
  }
  for (const child of all(step, "step")) {
    if (!empty(child)) {
      return false;
    }
  }
  return true;
}

// The stage of a page in the process flow, from 1 to 5. The page is a node of the case study document, with
// its steps in it. The level is 0 for the case study, 1 for a question, and one more for each step below.
// A page with steps that are not empty has the stage of its level. This is 1 for the case study, 2 for a
// question, 3 for a process flow step and 4 for the steps below. A page without such steps has stage 5 when
// it has tools, methods, models or data. Other pages also have the stage of their level.
//
//   stageOf(caseStudy, 0);  // 1
//   stageOf(step, 2);       // 3 for a step with steps, 5 for a step with only tools and data
export function stageOf(page, level) {
  let steps = false;
  for (const child of all(page, level === 0 ? "regulatoryQuestion" : "step")) {
    steps = steps || !empty(child);
  }
  if (!steps && (all(page, "tool").length || all(page, "supply").length)) {
    return 5;
  }
  return Math.min(level + 1, 4);
}

// The pages from the case study to the one in view. The path ends at an address the document no longer
// has, such as a removed or moved step.
function pages(state) {
  const found = [state.document];
  for (const address of state.path) {
    let next = null;
    for (const child of children(state, found[found.length - 1], found.length - 1)) {
      if (child["@id"] === address) {
        next = child;
        break;
      }
    }
    if (!next) {
      break;
    }
    found.push(next);
  }
  state.path = state.path.slice(0, found.length - 1);
  return found;
}

// The addresses from the case study down to a page; null when it is not found.
function pathTo(state, page, level, address) {
  if (level > DEEPEST) {
    return null;
  }
  for (const child of children(state, page, level)) {
    if (child["@id"] === address) {
      return [address];
    }
    const below = pathTo(state, child, level + 1, address);
    if (below) {
      return [child["@id"]].concat(below);
    }
  }
  return null;
}

// Platform addresses are linked on this server, so they work on every copy of the platform.
function local(address, options) {
  return options.base && address.startsWith(options.base) ? "/" + address.slice(options.base.length) : address;
}

function opens(link, options) {
  if (options.linkTarget) {
    link.target = options.linkTarget;
    link.rel = "noopener noreferrer";
  }
}

// A text's HTML without what could run code or change the page around it: scripts and the like, event
// attributes (onclick), and javascript: addresses.
function safeHtml(text, options) {
  const parsed = new DOMParser().parseFromString(text, "text/html");
  for (const element of parsed.body.querySelectorAll(UNSAFE)) {
    element.remove();
  }
  for (const element of parsed.body.querySelectorAll("*")) {
    for (const attribute of Array.from(element.attributes)) {
      const value = attribute.value.replace(/[\s\u0000-\u001f]/g, "").toLowerCase();
      if (attribute.name.toLowerCase().startsWith("on") || attribute.name.toLowerCase() === "srcdoc" || value.startsWith("javascript:")) {
        element.removeAttribute(attribute.name);
      }
    }
    if (element.tagName === "A") {
      opens(element, options);
    }
  }
  const fragment = document.createDocumentFragment();
  while (parsed.body.firstChild) {
    fragment.append(parsed.body.firstChild);
  }
  return fragment;
}

// Breadcrumbs: the case studies, the case study, and the pages down to the one in view.
function breadcrumbs(container, state, found) {
  const nav = make("nav", "navbar navbar-expand-lg bg-body-tertiary");
  nav.setAttribute("aria-label", "breadcrumb");
  nav.style.setProperty("--bs-breadcrumb-divider", "'/'");
  const list = make("ol", "breadcrumb p-3 m-0");
  const listed = make("a", "", "Case Studies");
  listed.href = "/casestudies";
  opens(listed, state.options);
  const item = make("li", "breadcrumb-item");
  item.append(listed);
  list.append(item);
  for (let level = 0; level < found.length; level += 1) {
    const name = first(found[level], "name") || "(no name)";
    if (level === found.length - 1) {
      const here = make("li", "breadcrumb-item active text-vhppink-distinct", name);
      here.dataset.field = "name";
      here.setAttribute("aria-current", "page");
      list.append(here);
    } else {
      const crumb = make("li", "breadcrumb-item");
      const link = make("a", "", name);
      link.href = "#";
      link.addEventListener("click", function (event) {
        event.preventDefault();
        navigate(container, state.path.slice(0, level));
      });
      crumb.append(link);
      list.append(crumb);
    }
  }
  nav.append(list);
  return nav;
}

// The process flow. The stage of the page in view is active. The stages of the pages above it are completed,
// and a click on one of them opens that page. The other stages before the active one are skipped.
function processFlow(container, state, found) {
  const level = found.length - 1;
  const active = stageOf(found[level], level);
  // The level of the page above at each stage; the lowest page is kept.
  const above = [];
  for (let at = 0; at < level; at += 1) {
    above[stageOf(found[at], at)] = at;
  }
  const header = make("div", "workflow-header");
  header.append(make("h5", "", "Process Flow"));
  const tracker = make("div", "step-tracker");
  for (let step = 1; step <= PROCESS_FLOW.length; step += 1) {
    if (step > 1) {
      tracker.append(make("div", "step-line"));
    }
    const item = make("div", "step-item");
    item.dataset.step = step;
    if (step === active) {
      item.classList.add("active");
    } else if (above[step] !== undefined) {
      item.classList.add("completed");
      item.addEventListener("click", function () {
        navigate(container, state.path.slice(0, above[step]));
      });
    } else if (step < active) {
      item.classList.add("skipped");
      item.title = "Skipped: not used on this path";
    }
    item.append(make("div", "step-icon", String(step)), make("span", "step-text", PROCESS_FLOW[step - 1]));
    tracker.append(item);
  }
  header.append(tracker);
  return header;
}

// A page's tools and methods, then its data, by name: each a link to its record, or a name without one. Each use
// is a part (HowToTool, HowToSupply) whose item is the record.
function items(state, page) {
  const found = [];
  for (const name of ["tool", "supply"]) {
    const listed = [];
    for (const given of all(page, name)) {
      // A use given by address only, as in flat JSON-LD, is found by its address.
      const part = given && typeof given === "object" && given.item === undefined && given["@id"] ? state.nodes.get(given["@id"]) || given : given;
      const value = part && typeof part === "object" && part.item !== undefined ? all(part, "item")[0] : part;
      if (value && typeof value === "object" && value["@id"]) {
        const record = state.nodes.get(value["@id"]) || value;
        listed.push({ name: first(record, "name") || value["@id"].split("/").pop(), address: value["@id"], field: name });
      } else if (value && typeof value === "object") {
        listed.push({ name: first(value, "@value"), address: "", field: name });
      } else {
        listed.push({ name: String(value), address: "", field: name });
      }
    }
    listed.sort(function (one, other) {
      return one.name.localeCompare(other.name, undefined, { numeric: true });
    });
    for (const item of listed) {
      found.push(item);
    }
  }
  return found;
}

function column(button) {
  const cell = make("div", "col-md pb-2 d-flex align-items-stretch");
  cell.append(button);
  return cell;
}

// The buttons of a page. The pages one level down come first, in order. Then the tools, methods and data come,
// each linked to its page. Empty steps are left out, or greyed in the preview.
function buttons(container, state, page, level) {
  const row = make("div", "row py-3");
  for (const child of children(state, page, level)) {
    const hidden = empty(child);
    if (hidden && !state.options.openDisabled) {
      continue;
    }
    const button = make("button", "btn w-100 text-white " + BUTTONS[Math.min(level, BUTTONS.length - 1)]);
    button.type = "button";
    button.append(make("b", "", label(state, child) || child["@id"] || "(no name)"));
    // A question's button has the question under its title.
    if (level === 0 && first(child, "text")) {
      button.append(make("br"), document.createTextNode(first(child, "text")));
    }
    const disabled = first(child, "creativeWorkStatus") === "disabled";
    if (disabled || hidden) {
      button.classList.add("opacity-25");
    }
    if (disabled && !state.options.openDisabled) {
      button.classList.add("disabled");
      button.disabled = true;
    } else if (child["@id"]) {
      if (hidden) {
        button.title = "Empty: hidden on the website";
      } else if (disabled) {
        button.title = "Greyed out on the website, and not opened there";
      }
      button.addEventListener("click", function () {
        navigate(container, state.path.concat([child["@id"]]));
      });
    }
    row.append(column(button));
  }
  for (const item of items(state, page)) {
    const button = make(item.address ? "a" : "button", "btn w-100 text-white " + ITEMS);
    button.dataset.field = item.field;
    button.dataset.value = item.address || item.name || "";
    if (item.address) {
      button.href = local(item.address, state.options);
      opens(button, state.options);
    } else {
      button.type = "button";
      button.title = "No record on the platform yet";
    }
    button.append(make("b", "", item.name || "(no name)"));
    const cell = column(button);
    // When onPick is set, the button is picked, and the link is opened by an icon beside it.
    if (item.address && state.options.onPick) {
      const open = make("a", "case-study-open align-self-center", "↗");
      open.href = local(item.address, state.options);
      open.target = "_blank";
      open.rel = "noopener";
      open.title = "Open in a new tab";
      cell.append(open);
    }
    row.append(cell);
  }
  return row;
}

// A page's sections as an accordion, in order: the first open on a new page, else those open before.
function sections(state, page) {
  const accordion = make("div", "accordion");
  accordion.id = state.id + "-sections";
  // A hidden section is not shown on the website; the preview shows it greyed.
  const found = parts(state, page, "hasPart").filter(function (section) {
    return first(section, "creativeWorkStatus") !== "hidden" || state.options.openDisabled;
  });
  for (let count = 0; count < found.length; count += 1) {
    const key = (page["@id"] || "") + " " + count;
    const open = state.open.has(key) ? state.open.get(key) : count === 0;
    const id = state.id + "-section-" + count;
    const item = make("div", "accordion-item" + (first(found[count], "creativeWorkStatus") === "hidden" ? " opacity-50" : ""));
    item.dataset.position = first(found[count], "position");
    item.dataset.name = first(found[count], "name");
    const header = make("h2", "accordion-header");
    const toggle = make("button", "accordion-button" + (open ? "" : " collapsed"), first(found[count], "name") || "Section " + (count + 1));
    toggle.type = "button";
    toggle.dataset.field = "name";
    toggle.dataset.bsToggle = "collapse";
    toggle.dataset.bsTarget = "#" + id;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.setAttribute("aria-controls", id);
    header.append(toggle);
    const body = make("div", "accordion-collapse collapse" + (open ? " show" : ""));
    body.id = id;
    body.dataset.key = key;
    body.dataset.bsParent = "#" + accordion.id;
    const text = make("div", "accordion-body");
    text.dataset.field = "text";
    text.append(safeHtml(first(found[count], "text"), state.options));
    body.append(text);
    item.append(header, body);
    accordion.append(item);
  }
  return accordion;
}

// A step's inputs and outputs, by name, in a box of their own.
function parameters(state, page) {
  const box = make("div", "case-study-parameters card mb-4");
  const body = make("div", "card-body py-2");
  for (const [name, label] of [["bioschemas:input", "Input"], ["bioschemas:output", "Output"]]) {
    const found = parts(state, page, name);
    if (found.length) {
      const line = make("div", "");
      line.dataset.field = name.split(":").pop();
      line.append(make("strong", "", label + ": "), document.createTextNode(found.map(function (part) { return first(part, "name"); }).join("; ")));
      body.append(line);
    }
  }
  box.append(body);
  return body.children.length ? box : null;
}

// A page: heading, summary, buttons, text, inputs and outputs, and sections. It slides in from its side, as
// on the website.
function view(container, state, page, level, direction) {
  const shown = make("div", "case-study-page py-md-5 py-3" + (direction ? " case-study-" + direction : ""));
  const top = make("div", "container");
  // A question's page has a heading of its own; the case study's summary is its introduction.
  let heading = first(page, "name");
  let summary = first(page, "description");
  if (level === 0) {
    summary = first(page, "abstract") || summary;
  } else if (level === 1) {
    heading = first(page, "headline") || heading;
  }
  const title = make("h1", HEADINGS[Math.min(level, HEADINGS.length - 1)], heading || "(no name)");
  title.dataset.field = level === 1 ? "headline name" : "name";
  top.append(title);
  if (summary) {
    const introduction = make("p", "text-secondary fs-5", summary);
    introduction.dataset.field = level === 0 ? "abstract description" : "description";
    top.append(introduction);
  }
  const row = buttons(container, state, page, level);
  if (row.children.length) {
    top.append(row);
  }
  const bottom = make("div", "container");
  if (first(page, "text")) {
    const text = make("div", "case-study-text mb-4");
    text.dataset.field = "text";
    text.append(safeHtml(first(page, "text"), state.options));
    bottom.append(text);
  }
  const given = parameters(state, page);
  if (given) {
    bottom.append(given);
  }
  bottom.append(sections(state, page));
  shown.append(top, bottom);
  return shown;
}

// The open sections, read before the container is drawn again.
function rememberOpen(container, state) {
  for (const body of container.querySelectorAll(".accordion-collapse[data-key]")) {
    state.open.set(body.dataset.key, body.classList.contains("show"));
  }
}

// The form's section on the page in view: by position and name, else by position, else by name.
function sectionOf(container, section) {
  let found = null;
  let fit = 0;
  for (const item of container.querySelectorAll(".accordion-item")) {
    const fits = (parseFloat(item.dataset.position) === parseFloat(section.position) ? 2 : 0) + (item.dataset.name === section.name ? 1 : 0);
    if (fits > fit) {
      found = item;
      fit = fits;
    }
  }
  return found;
}

// The elements that show the marked field on the page in view. A section's field is marked in its opened
// section; a field the page does not show marks the whole section.
function mark(container, state) {
  for (const marked of container.querySelectorAll(".case-study-mark")) {
    marked.classList.remove("case-study-mark");
  }
  const here = state.path.length ? state.path[state.path.length - 1] : state.document["@id"];
  if (!state.mark || state.mark.address !== here) {
    return;
  }
  let section = null;
  if (state.mark.section) {
    section = sectionOf(container, state.mark.section);
    if (!section) {
      return;
    }
    const body = section.querySelector(".accordion-collapse");
    const toggle = section.querySelector(".accordion-button");
    body.classList.add("show");
    toggle.classList.remove("collapsed");
    toggle.setAttribute("aria-expanded", "true");
  }
  let marked = 0;
  for (const element of container.querySelectorAll("[data-field]")) {
    if (element.dataset.field.split(" ").includes(state.mark.field) && element.closest(".accordion-item") === section) {
      element.classList.add("case-study-mark");
      marked += 1;
    }
  }
  if (section && !marked) {
    section.classList.add("case-study-mark");
  }
}

// The container scrolls to the mark when it is out of view; the window does not move.
function reveal(container) {
  const marked = container.querySelector(".case-study-mark");
  if (!marked) {
    return;
  }
  const box = container.getBoundingClientRect();
  const at = marked.getBoundingClientRect();
  if (at.top < box.top || at.bottom > box.bottom) {
    container.scrollTop += at.top - box.top - 16;
  }
}

function draw(container, direction) {
  const state = states.get(container);
  rememberOpen(container, state);
  const found = pages(state);
  const level = found.length - 1;
  const shown = make("div", "case-study");
  shown.append(breadcrumbs(container, state, found), processFlow(container, state, found), view(container, state, found[level], level, direction));
  container.replaceChildren(shown);
  mark(container, state);
}

function navigate(container, path) {
  const state = states.get(container);
  let direction = "";
  if (path.length > state.path.length) {
    direction = "deeper";
  } else if (path.length < state.path.length) {
    direction = "back";
  }
  state.path = path;
  draw(container, direction);
  if (state.options.onNavigate) {
    state.options.onNavigate(state.path.length ? state.path[state.path.length - 1] : state.document["@id"]);
  }
}

// Draws a case study's document in a container. Drawn again with a new document, such as one with an
// editor's changes, it stays on its page and keeps its sections open.
export function renderCaseStudy(container, caseStudy, options) {
  let state = states.get(container);
  if (!state) {
    containers += 1;
    state = { id: "case-study-" + containers, path: [], open: new Map() };
    states.set(container, state);
    // Told after the buttons of the page have done their part, such as opening another page. The icon that
    // opens a link in a new tab is not picked.
    container.addEventListener("click", function (event) {
      const picked = states.get(container);
      if (!picked.options.onPick || event.target.closest(".case-study-open")) {
        return;
      }
      if (event.target.closest("a[href]")) {
        event.preventDefault();
      }
      const field = event.target.closest("[data-field]");
      const item = event.target.closest(".accordion-item");
      const section = item ? { position: item.dataset.position, name: item.dataset.name } : null;
      const here = picked.path.length ? picked.path[picked.path.length - 1] : picked.document["@id"];
      picked.options.onPick(here, field ? field.dataset.field : "", section, field ? field.dataset.value || "" : "");
    });
  }
  state.document = caseStudy || {};
  state.options = options || {};
  state.nodes = index(state.document, new Map());
  if (state.options.at) {
    state.path = pathTo(state, state.document, 0, state.options.at) || [];
  }
  draw(container, "");
}

// Marks what shows a field of the page at an address, or of its section ({position, name}), and opens that
// page. The mark stays when the container is drawn again.
export function markField(container, address, field, section) {
  const state = states.get(container);
  if (!state) {
    return;
  }
  state.mark = { address: address, field: field, section: section };
  const path = address === state.document["@id"] ? [] : pathTo(state, state.document, 0, address);
  if (path && path.join(" ") !== state.path.join(" ")) {
    navigate(container, path);
  } else {
    mark(container, state);
  }
  reveal(container);
}
