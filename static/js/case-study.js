// A case study as the platform's website shows it, drawn from its JSON-LD document: the one of
// GET /api/casestudies/<case>, or the one that the editor's preview gives for changes not saved yet.
// The pages of a case study are levels, one in view at a time: the case study with its regulatory
// questions, the page of a question with its process flow steps, then the pages of the steps and of their
// own steps. Each page has a heading, a summary, the buttons of the pages one level down and of the tools,
// methods and data it uses (links to their records), and its text in sections. The buttons, the
// breadcrumbs and the process flow lead from page to page in place, and a container drawn again with a
// new document stays on its page.
//
//   import { renderCaseStudy } from "/static/js/case-study.js";
//   renderCaseStudy(container, caseStudy, options);
//
// The options, all of them optional:
//   base         the platform's base address; links to the platform are made from this server, so that
//                they work on every copy of the platform
//   at           the address of the page to show, such as the one of the website's address; without it,
//                the container stays on the page it shows
//   linkTarget   where links open, such as "_blank" in the editor, so that it is not left
//   openDisabled true opens the pages whose buttons the website shows greyed out, to preview them
//   onNavigate   a function called with the address of the page in view, after a click opens another

// The colour of the heading of a page, by its level: the case study, a question, a process flow step, a
// step of one, and the steps below.
const HEADINGS = ["text-vhppink-distinct", "text-vhpdarkpurple", "text-vhpdarkteal", "text-vhplightteal", "text-vhpblue", "text-vhplightteal"];
// The colour of the buttons of a page that open the pages one level down: its questions, its process
// flow steps, its steps, and its sub-steps. The tools, methods and data that a page uses are blue.
const BUTTONS = ["btn-vhppink-distinct", "btn-vhpdarkpurple", "btn-vhpdarkteal", "btn-vhplightteal"];
const ITEMS = "btn-vhpblue";
const PROCESS_FLOW = ["Regulatory Question", "Safety Assessment Workflow Step", "Case Study Step", "Case Study Substep", "Tools, Models and Data"];
// The elements of a text that are left out, as they run code or change the page around the text.
const UNSAFE = "script, style, iframe, frame, frameset, object, embed, link, meta, base, form";
// The pages of a case study are not expected this deep; a document whose steps hold their own page is.
const DEEPEST = 20;

// What each container shows: the document, the addresses of the pages from the case study to the one
// in view, and the sections that are open.
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

// The values of a field: a document gives one value as itself, and several as a list.
function all(node, name) {
  const given = node ? node[name] : undefined;
  if (given === undefined || given === null) {
    return [];
  }
  return Array.isArray(given) ? given : [given];
}

// The first value of a field as a text: a typed value ({"@value": "1"}) gives its value, a link its address.
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

// The nodes of a document by their address, so that a node given only by its address ({"@id": ...}) is
// found where the document holds it: a document holds a node at the first link to it only, such as a
// tool that two steps use.
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

// Pages, sections and items are in the order of their position, then of their name.
function byPosition(one, other) {
  if (number(one) !== number(other)) {
    return number(one) < number(other) ? -1 : 1;
  }
  return first(one, "name").localeCompare(first(other, "name"), undefined, { numeric: true });
}

// The nodes of a field of a page, such as its steps or its sections, in order.
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

// The pages one level down from a page: the questions of the case study, or the steps of a page below.
function children(state, page, level) {
  return parts(state, page, level === 0 ? "regulatoryQuestion" : "step");
}

// The pages from the case study to the one in view. The path ends where the document no longer has the
// page of an address, such as a step that was removed or given another address.
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

// The addresses of the pages from the case study down to the page at an address; null when it has none.
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

// A platform address is linked from this server, so that it works on every copy of the platform.
function local(address, options) {
  return options.base && address.startsWith(options.base) ? "/" + address.slice(options.base.length) : address;
}

function opens(link, options) {
  if (options.linkTarget) {
    link.target = options.linkTarget;
    link.rel = "noopener noreferrer";
  }
}

// The HTML of a text, as an editor typed it, without what could run code or change the page around it:
// scripts and the like, the attributes of events (onclick), and javascript: addresses.
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

// The breadcrumbs: the list of case studies, the case study, and the pages down to the one in view.
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

// The process flow: where the page in view is in the workflow. Its earlier levels lead back to them.
function processFlow(container, state, level) {
  const header = make("div", "workflow-header");
  header.append(make("h5", "", "Process Flow"));
  const tracker = make("div", "step-tracker");
  for (let step = 1; step <= PROCESS_FLOW.length; step += 1) {
    if (step > 1) {
      tracker.append(make("div", "step-line"));
    }
    const item = make("div", "step-item");
    item.dataset.step = step;
    if (step < level + 1) {
      item.classList.add("completed");
    } else if (step === level + 1) {
      item.classList.add("active");
    }
    item.append(make("div", "step-icon", String(step)), make("span", "step-text", PROCESS_FLOW[step - 1]));
    if (step <= level) {
      item.addEventListener("click", function () {
        navigate(container, state.path.slice(0, step - 1));
      });
    }
    tracker.append(item);
  }
  header.append(tracker);
  return header;
}

// The tools and methods that a page uses, then its data, each in the order of their names: a link to the
// record on the platform, with the record's name, or the name of an item that has no record yet.
function items(state, page) {
  const found = [];
  for (const name of ["tool", "supply"]) {
    const listed = [];
    for (const value of all(page, name)) {
      if (value && typeof value === "object" && value["@id"]) {
        const record = state.nodes.get(value["@id"]) || value;
        listed.push({ name: first(record, "name") || value["@id"].split("/").pop(), address: value["@id"] });
      } else if (value && typeof value === "object") {
        listed.push({ name: first(value, "@value"), address: "" });
      } else {
        listed.push({ name: String(value), address: "" });
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

// The buttons of a page: the pages one level down, in order, and the tools, methods and data it uses,
// each linking to its page on the platform.
function buttons(container, state, page, level) {
  const row = make("div", "row py-3");
  for (const child of children(state, page, level)) {
    const button = make("button", "btn w-100 text-white " + BUTTONS[Math.min(level, BUTTONS.length - 1)]);
    button.type = "button";
    button.append(make("b", "", first(child, "name") || child["@id"] || "(no name)"));
    // A question's button has the question under its title.
    if (level === 0 && first(child, "text")) {
      button.append(make("br"), document.createTextNode(first(child, "text")));
    }
    const disabled = first(child, "creativeWorkStatus") === "disabled";
    if (disabled) {
      button.classList.add("opacity-25");
    }
    if (disabled && !state.options.openDisabled) {
      button.classList.add("disabled");
      button.disabled = true;
    } else if (child["@id"]) {
      if (disabled) {
        button.title = "The website shows this button greyed out, and does not open its page";
      }
      button.addEventListener("click", function () {
        navigate(container, state.path.concat([child["@id"]]));
      });
    }
    row.append(column(button));
  }
  for (const item of items(state, page)) {
    const button = make(item.address ? "a" : "button", "btn w-100 text-white " + ITEMS);
    if (item.address) {
      button.href = local(item.address, state.options);
      opens(button, state.options);
    } else {
      button.type = "button";
      button.title = "It has no record on the platform yet";
    }
    button.append(make("b", "", item.name || "(no name)"));
    row.append(column(button));
  }
  return row;
}

// The sections of a page as an accordion, in order. The first one is open on a page not seen before;
// on a page drawn again, those that were open.
function sections(state, page) {
  const accordion = make("div", "accordion");
  accordion.id = state.id + "-sections";
  const found = parts(state, page, "hasPart");
  for (let count = 0; count < found.length; count += 1) {
    const key = (page["@id"] || "") + " " + count;
    const open = state.open.has(key) ? state.open.get(key) : count === 0;
    const id = state.id + "-section-" + count;
    const item = make("div", "accordion-item");
    const header = make("h2", "accordion-header");
    const toggle = make("button", "accordion-button" + (open ? "" : " collapsed"), first(found[count], "name") || "Section " + (count + 1));
    toggle.type = "button";
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
    text.append(safeHtml(first(found[count], "text"), state.options));
    body.append(text);
    item.append(header, body);
    accordion.append(item);
  }
  return accordion;
}

// A page: its heading and summary, its buttons, then its text and its sections. It slides in from the
// side it comes from, as the website's pages do.
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
  top.append(make("h1", HEADINGS[Math.min(level, HEADINGS.length - 1)], heading || "(no name)"));
  if (summary) {
    top.append(make("p", "text-secondary fs-5", summary));
  }
  const row = buttons(container, state, page, level);
  if (row.children.length) {
    top.append(row);
  }
  const bottom = make("div", "container");
  if (first(page, "text")) {
    const text = make("div", "case-study-text mb-4");
    text.append(safeHtml(first(page, "text"), state.options));
    bottom.append(text);
  }
  bottom.append(sections(state, page));
  shown.append(top, bottom);
  return shown;
}

// The sections that are open, read before the container is drawn again.
function rememberOpen(container, state) {
  for (const body of container.querySelectorAll(".accordion-collapse[data-key]")) {
    state.open.set(body.dataset.key, body.classList.contains("show"));
  }
}

function draw(container, direction) {
  const state = states.get(container);
  rememberOpen(container, state);
  const found = pages(state);
  const level = found.length - 1;
  const shown = make("div", "case-study");
  shown.append(breadcrumbs(container, state, found), processFlow(container, state, level), view(container, state, found[level], level, direction));
  container.replaceChildren(shown);
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
// editor's changes, the container stays on the page it shows, and keeps open the sections that are.
export function renderCaseStudy(container, caseStudy, options) {
  let state = states.get(container);
  if (!state) {
    containers += 1;
    state = { id: "case-study-" + containers, path: [], open: new Map() };
    states.set(container, state);
  }
  state.document = caseStudy || {};
  state.options = options || {};
  state.nodes = index(state.document, new Map());
  if (state.options.at) {
    state.path = pathTo(state, state.document, 0, state.options.at) || [];
  }
  draw(container, "");
}
