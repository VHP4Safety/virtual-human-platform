// Drawing of a case study from its JSON-LD document, as on the website.

// Heading colours by level, from the case study down to the deeper steps.
const HEADINGS = ["text-vhppink-distinct", "text-vhpdarkpurple", "text-vhpdarkteal", "text-vhplightteal", "text-vhpblue", "text-vhplightteal"];
// Colours of the buttons to the pages one level down, by level.
// Tools, methods and data are blue.
const BUTTONS = ["btn-vhppink-distinct", "btn-vhpdarkpurple", "btn-vhpdarkteal", "btn-vhplightteal"];
const ITEMS = "btn-vhpblue";
const PROCESS_FLOW = ["Regulatory Question", "Safety Assessment Workflow Step", "Case Study Step", "Case Study Substep", "Tools, Models and Data"];
// The fields with content for a step.
const CONTENT = ["tool", "supply", "bioschemas:input", "bioschemas:output", "hasPart", "text", "description"];
// The elements that are removed from a text, so that no code is run and the page around the text is not changed.
const UNSAFE = "script, style, iframe, frame, frameset, object, embed, link, meta, base, form";
// The deepest level that is searched. Only steps with their own page are searched deeper.
const DEEPEST = 20;

// The state of each container, with the document, the path to the page in view, the open sections and the mark.
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

// Return the values of a field as a list, also if the document has one value without a list.
function all(node, name) {
  const given = node ? node[name] : undefined;
  if (given === undefined || given === null) {
    return [];
  }
  return Array.isArray(given) ? given : [given];
}

// Return the first value of a field of a node as a text.
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

// Index the nodes of a document by address.
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

// Order pages, sections and items by position, then by name.
function byPosition(one, other) {
  if (number(one) !== number(other)) {
    return number(one) < number(other) ? -1 : 1;
  }
  return first(one, "name").localeCompare(first(other, "name"), undefined, { numeric: true });
}

// Return the nodes of a field of a page, such as steps or sections, in order.
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

// Return the label of the button of a page.
function label(state, node) {
  if (first(node, "name")) {
    return first(node, "name");
  }
  for (const value of all(node, "additionalType")) {
    const term = value && typeof value === "object" ? state.nodes.get(value["@id"]) || value : null;
    const name = term ? first(term, "name") : "";
    if (name) {
      return name.replace(/\s*\([^)]*\)$/, "");
    }
  }
  return first(node, "name");
}

// Return the pages one level down, which are questions or steps. The questions of a case study are its parts that are pages of
// their own; its other parts are the sections of its page.
function children(state, page, level) {
  return parts(state, page, level === 0 ? "hasPart" : "step").filter(function (node) { return level !== 0 || !isPart(String(node["@id"] || "_:")); });
}

// Return true if a step has no content and no steps with content.
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

// Return true for a part of a record, which has no page of its own.
function isPart(id) {
  return id.startsWith("_:") || /#[A-Za-z_][A-Za-z0-9_]*-[0-9]+$/.test(id);
}

// Return the stage of a page in the process flow, from 1 to 5.
export function stageOf(page, level) {
  let steps = false;
  for (const child of all(page, level === 0 ? "hasPart" : "step")) {
    if (level !== 0 || (child && typeof child === "object" && !isPart(String(child["@id"] || "_:")))) {
      steps = steps || !empty(child);
    }
  }
  if (!steps && (all(page, "tool").length || all(page, "supply").length)) {
    return 5;
  }
  return Math.min(level + 1, 4);
}

// Return the pages from the case study to the page in view.
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

// Return the addresses from the case study down to a page, or null if the page is not found.
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

// Return a platform address as an address on this server.
// A value that is not an http, https or mailto address or a path, such as a javascript: address in a text, links nowhere.
function local(address, options) {
  const plain = address.replace(/[\s\u0000-\u001f]/g, "");
  if (/^[^/?#]*:/.test(plain) && !/^(https?|mailto):/i.test(plain)) {
    return "#";
  }
  return options.base && address.startsWith(options.base) ? "/" + address.slice(options.base.length) : address;
}

function opens(link, options) {
  if (options.linkTarget) {
    link.target = options.linkTarget;
    link.rel = "noopener noreferrer";
  }
}

// Return the HTML of a text without scripts, event attributes and javascript: addresses.
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
      // A link to the platform is opened on this server.
      if (element.hasAttribute("href")) {
        element.setAttribute("href", local(element.getAttribute("href"), options));
      }
      opens(element, options);
    }
    // An image on the platform is loaded from this server, as links are.
    if (element.tagName === "IMG" && element.getAttribute("src")) {
      element.setAttribute("src", local(element.getAttribute("src"), options));
    }
  }
  const fragment = document.createDocumentFragment();
  while (parsed.body.firstChild) {
    fragment.append(parsed.body.firstChild);
  }
  return fragment;
}

// Draw the breadcrumbs down to the page in view.
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

// Draw the process flow, with the stage of the page in view active.
function processFlow(container, state, found, header) {
  const level = found.length - 1;
  const active = stageOf(found[level], level);
  // The level of the lowest page above the page in view at each stage.
  const above = [];
  for (let at = 0; at < level; at += 1) {
    above[stageOf(found[at], at)] = at;
  }
  // The header is drawn once and then only marked, so that marks in it, such as the glossary marks, are kept.
  if (!header) {
    header = make("div", "workflow-header");
    header.append(make("h5", "", "Process Flow"));
    const tracker = make("div", "step-tracker");
    for (let step = 1; step <= PROCESS_FLOW.length; step += 1) {
      if (step > 1) {
        tracker.append(make("div", "step-line"));
      }
      const item = make("div", "step-item");
      item.dataset.step = step;
      item.append(make("div", "step-icon", String(step)), make("span", "step-text", PROCESS_FLOW[step - 1]));
      // The pages of a stage after the questions roll out from the button under the stage.
      if (step > 1) {
        const more = make("button", "step-more");
        more.type = "button";
        more.setAttribute("aria-expanded", "false");
        more.setAttribute("aria-controls", state.id + "-rollout");
        more.addEventListener("click", function (event) {
          event.stopPropagation();
          rollOut(container, header, step);
        });
        item.append(more);
      }
      tracker.append(item);
    }
    header.append(tracker);
    const rollout = make("div", "step-rollout");
    rollout.id = state.id + "-rollout";
    rollout.append(make("div", "step-rollout-inner"));
    header.append(rollout);
  }
  // The pages of each stage are counted again with each drawing, also when the document has changed, as in the editor
  // preview, and the pages that are out are rolled in.
  const counts = [];
  for (const value of staged(state)) {
    counts[value.stage] = (counts[value.stage] || 0) + 1;
  }
  for (const more of header.querySelectorAll(".step-more")) {
    const step = Number(more.closest(".step-item").dataset.step);
    more.replaceChildren(document.createTextNode(String(counts[step] || 0) + " "), make("i", "bi bi-chevron-down"));
    more.title = "The pages of this stage in the case study";
    more.hidden = !counts[step];
    more.setAttribute("aria-expanded", "false");
  }
  header.querySelector(".step-rollout").classList.remove("open");
  for (const item of header.querySelectorAll(".step-item")) {
    const step = Number(item.dataset.step);
    item.classList.toggle("active", step === active);
    item.classList.toggle("completed", step !== active && above[step] !== undefined);
    item.classList.toggle("skipped", step !== active && above[step] === undefined && step < active);
    item.title = item.classList.contains("skipped") ? "Skipped: not used on this path" : "";
    item.onclick = item.classList.contains("completed") ? function () { navigate(container, state.path.slice(0, above[step])); } : null;
  }
  return header;
}

// Return the pages of the case study and their tools, models and data, each with the stage of the process flow at which
// it is chosen, the addresses down to the page, the page above it and its question. The pages that have no button on
// the website are left out, as are the pages below a greyed-out page.
function staged(state) {
  const found = [];
  function walk(page, level, path, question) {
    for (const child of level < DEEPEST ? children(state, page, level) : []) {
      const greyed = first(child, "creativeWorkStatus") === "Incomplete";
      if (!child["@id"] || (empty(child) && !greyed && !state.options.openDisabled)) {
        continue;
      }
      const asked = level === 0 ? label(state, child) || child["@id"] : question;
      const disabled = greyed && !state.options.openDisabled;
      found.push({ stage: stageOf(page, level), path: path.concat([child["@id"]]), name: label(state, child) || child["@id"],
                   above: level ? label(state, page) : "", question: asked, disabled: disabled, page: true });
      if (!disabled) {
        walk(child, level + 1, path.concat([child["@id"]]), asked);
      }
    }
    for (const item of level ? items(state, page) : []) {
      found.push({ stage: PROCESS_FLOW.length, path: path, name: item.name || "(no name)", above: label(state, page), question: question,
                   disabled: false, page: false });
    }
  }
  walk(state.document, 0, [], "");
  return found;
}

// Roll out the pages of a stage under the process flow, or roll them in if they are out.
function rollOut(container, header, step) {
  const state = states.get(container);
  const rollout = header.querySelector(".step-rollout");
  const opening = !(rollout.classList.contains("open") && rollout.dataset.step === String(step));
  for (const more of header.querySelectorAll(".step-more")) {
    more.setAttribute("aria-expanded", String(opening && more.closest(".step-item").dataset.step === String(step)));
  }
  if (!opening) {
    rollout.classList.remove("open");
    return;
  }
  rollout.dataset.step = step;
  const body = stagePages(container, state, step);
  rollout.firstElementChild.replaceChildren(body);
  // The pointer of the panel is under the button of the stage.
  const item = header.querySelector('.step-item[data-step="' + step + '"]').getBoundingClientRect();
  const box = body.getBoundingClientRect();
  body.style.setProperty("--pointer", Math.min(Math.max(item.left + item.width / 2 - box.left, 16), box.width - 16) + "px");
  rollout.classList.add("open");
}

// Return the panel of the pages of a stage, by question, each as a button in the colour of the stage that opens its page
// as if its branch were clicked through. A tool, model or data opens the page that lists it.
function stagePages(container, state, step) {
  const body = make("div", "step-rollout-body");
  const colour = step < PROCESS_FLOW.length ? BUTTONS[step - 1] : ITEMS;
  const here = state.path.length ? state.path[state.path.length - 1] : "";
  const groups = new Map();
  for (const value of staged(state)) {
    if (value.stage === step) {
      groups.set(value.question, (groups.get(value.question) || []).concat([value]));
    }
  }
  for (const [question, values] of groups) {
    body.append(make("div", "step-rollout-question", question));
    const row = make("div", "d-flex flex-wrap gap-2");
    for (const value of values) {
      const current = value.page && value.path[value.path.length - 1] === here;
      const link = make(value.disabled ? "span" : "a", "btn btn-sm " + (current ? colour : colour.replace("btn-", "btn-outline-")));
      link.append(make("b", "", value.name));
      // The page above is named, as several pages have the same name, such as the Exposure of each question.
      if (value.above && step > 2) {
        link.append(make("span", "step-rollout-above", value.above));
      }
      if (value.disabled) {
        link.classList.add("disabled", "opacity-25");
        link.title = "Greyed out on the website, and not opened there";
      } else {
        link.href = local(value.path.length ? value.path[value.path.length - 1] : state.document["@id"] || "", state.options);
        link.addEventListener("click", function (event) {
          event.preventDefault();
          navigate(container, value.path);
        });
      }
      row.append(link);
    }
    body.append(row);
  }
  return body;
}

// Return the tools, methods and data of a page, by name.
function items(state, page) {
  const found = [];
  for (const name of ["tool", "supply"]) {
    for (const given of all(page, name)) {
      // A use given by address only, as in flat JSON-LD, is found by its address.
      const part = given && typeof given === "object" && given.item === undefined && given["@id"] ? state.nodes.get(given["@id"]) || given : given;
      const value = part && typeof part === "object" && part.item !== undefined ? all(part, "item")[0] : part;
      // The label and description of a use are used, else the name of the record.
      const use = part && typeof part === "object" && part.item !== undefined ? part : {};
      const item = { name: first(use, "name"), description: first(use, "description"), position: number(use), address: "", field: name };
      if (value && typeof value === "object" && value["@id"]) {
        const record = state.nodes.get(value["@id"]) || value;
        item.name = item.name || first(record, "name") || value["@id"].split("/").pop();
        item.address = value["@id"];
      } else if (value && typeof value === "object") {
        item.name = item.name || first(value, "@value");
      } else {
        item.name = item.name || String(value);
      }
      found.push(item);
    }
  }
  // The uses are in their order in the case study, and uses without a position are listed after them, by name.
  found.sort(function (one, other) {
    if (one.position !== other.position) {
      return one.position < other.position ? -1 : 1;
    }
    return one.name.localeCompare(other.name, undefined, { numeric: true });
  });
  return found;
}

function column(button) {
  const cell = make("div", "col-md pb-2 d-flex align-items-stretch");
  cell.append(button);
  return cell;
}

// Draw the buttons of a page.
function buttons(container, state, page, level) {
  const row = make("div", "row py-3");
  for (const child of children(state, page, level)) {
    const disabled = first(child, "creativeWorkStatus") === "Incomplete";
    const hidden = empty(child) && !disabled;
    if (hidden && !state.options.openDisabled) {
      continue;
    }
    const button = make("button", "btn w-100 text-white " + BUTTONS[Math.min(level, BUTTONS.length - 1)]);
    button.type = "button";
    button.append(make("b", "", label(state, child) || child["@id"] || "(no name)"));
    // The button of a question has the question under its title. Other buttons have their description.
    if (level === 0 && first(child, "text")) {
      button.append(make("br"), document.createTextNode(first(child, "text")));
    } else if (first(child, "disambiguatingDescription")) {
      button.append(make("br"), document.createTextNode(first(child, "disambiguatingDescription")));
    }
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
    // The label of a box is in its middle, with the description below the label, as on a button.
    const button = make(item.address ? "a" : "button", "btn w-100 text-white d-flex flex-column justify-content-center " + ITEMS);
    button.dataset.field = item.field;
    button.dataset.value = item.address || item.name || "";
    if (item.address) {
      button.href = local(item.address, state.options);
      opens(button, state.options);
    } else {
      button.type = "button";
    }
    button.append(make("b", "", item.name || "(no name)"));
    if (item.description) {
      const description = make("span", "");
      description.append(safeHtml(item.description, state.options));
      button.append(description);
    }
    const cell = column(button);
    // With onPick, a click picks the button, and the link is opened with the icon next to the button.
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

// Draw a section of the accordion of a page: its title, and its content when it is opened.
function accordionItem(state, accordion, key, title, content, open) {
  const id = accordion.id + "-" + accordion.children.length;
  const item = make("div", "accordion-item");
  const header = make("h2", "accordion-header");
  const toggle = make("button", "accordion-button" + (open ? "" : " collapsed"), title);
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
  const inner = make("div", "accordion-body");
  inner.append(content);
  body.append(inner);
  item.append(header, body);
  accordion.append(item);
  return item;
}

// Draw the sections of a page as an accordion.
function sections(state, page) {
  const accordion = make("div", "accordion");
  accordion.id = state.id + "-sections";
  // A hidden section is not shown on the website, and it is greyed out in the preview. A question is a page of its own,
  // not a section.
  const found = parts(state, page, "hasPart").filter(function (section) {
    return isPart(String(section["@id"] || "_:")) && (first(section, "creativeWorkStatus") !== "hidden" || state.options.openDisabled);
  });
  found.forEach(function (section, count) {
    const key = (page["@id"] || "") + " " + count;
    const open = state.open.has(key) ? state.open.get(key) : count === 0;
    const item = accordionItem(state, accordion, key, first(section, "name") || "Section " + (count + 1), safeHtml(first(section, "text"), state.options), open);
    item.classList.toggle("opacity-50", first(section, "creativeWorkStatus") === "hidden");
    item.dataset.position = first(section, "position");
    item.dataset.name = first(section, "name");
    item.querySelector(".accordion-button").dataset.field = "name";
    item.querySelector(".accordion-body").dataset.field = "text";
  });
  const given = parameters(state, page);
  if (given) {
    const key = (page["@id"] || "") + " parameters";
    accordionItem(state, accordion, key, "Input and resulting output", given, state.open.get(key) || false);
  }
  return accordion;
}

// Return the inputs and outputs of a page as its last section, or null.
function parameters(state, page) {
  const list = make("ul", "");
  for (const [name, label] of [["bioschemas:input", "Input"], ["bioschemas:output", "Output"]]) {
    let found = all(page, name).map(function (value) {
      return value && typeof value === "object" && value["@id"] ? state.nodes.get(value["@id"]) || value : value;
    });
    // A parameter with the HTML of the case study is shown with that HTML and its links, and its linked datasets are
    // not listed again.
    const written = found.map(function (value) { return first(value, "description"); }).filter(Boolean).join(" ");
    found = found.filter(function (value) {
      const address = value && value["@id"] && !isPart(value["@id"]) ? value["@id"] : "";
      return !address || !written.includes("/" + address.split("/").slice(-2).join("/"));
    });
    if (found.length) {
      const line = make("li", "");
      line.dataset.field = name.split(":").pop();
      line.append(make("strong", "", label + ":"), document.createTextNode(" "));
      found.forEach(function (value, at) {
        if (at) {
          line.append(document.createTextNode(", "));
        }
        const address = value && value["@id"] && !isPart(value["@id"]) ? value["@id"] : "";
        const text = first(value, "name") || (address ? address.split("/").pop() : "");
        if (address) {
          const link = make("a", "", text);
          link.href = local(address, state.options);
          opens(link, state.options);
          line.append(link);
        } else if (first(value, "description")) {
          line.append(safeHtml(first(value, "description"), state.options));
        } else {
          line.append(document.createTextNode(text));
        }
      });
      list.append(line);
    }
  }
  return list.children.length ? list : null;
}

// Draw a page.
function view(container, state, page, level) {
  const shown = make("div", "case-study-page");
  const top = make("div", "container");
  // The heading is the headline of the page, else its name. The summary of the case study is its introduction.
  const heading = first(page, "headline") || first(page, "name");
  let summary = first(page, "description");
  if (level === 0) {
    summary = first(page, "abstract") || summary;
  }
  const title = make("h1", HEADINGS[Math.min(level, HEADINGS.length - 1)], heading || "(no name)");
  title.dataset.field = "headline name";
  top.append(title);
  // The summary line is written also when it is empty.
  const introduction = make("p", "text-secondary fs-5", summary);
  introduction.dataset.field = level === 0 ? "abstract description" : "description";
  top.append(introduction);
  const row = buttons(container, state, page, level);
  if (row.children.length) {
    top.append(row);
  }
  const bottom = make("div", "container");
  // The question of a question page is on its button on the case study page, not again on its own page.
  if (level !== 1 && first(page, "text")) {
    const text = make("div", "case-study-text mb-4");
    text.dataset.field = "text";
    text.append(safeHtml(first(page, "text"), state.options));
    bottom.append(text);
  }
  bottom.append(sections(state, page));
  shown.append(top, bottom);
  return shown;
}

// Read the open sections before the container is drawn again.
function rememberOpen(container, state) {
  for (const body of container.querySelectorAll(".accordion-collapse[data-key]")) {
    state.open.set(body.dataset.key, body.classList.contains("show"));
  }
}

// Return the section of the form on the page in view, found by position and name.
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

// Mark the elements of the marked field on the page in view.
function mark(container, state) {
  for (const marked of container.querySelectorAll(".case-study-mark")) {
    marked.classList.remove("case-study-mark");
  }
  const here = state.path.length ? state.path[state.path.length - 1] : state.document["@id"];
  if (!state.mark || state.mark.address !== here) {
    return;
  }
  // The page in view is the panel with its address.
  const panel = container.querySelector('.case-study-panel[data-address="' + CSS.escape(here || "") + '"]') || container;
  let section = null;
  if (state.mark.section) {
    section = sectionOf(panel, state.mark.section);
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
  for (const element of panel.querySelectorAll("[data-field]")) {
    if (element.dataset.field.split(" ").includes(state.mark.field) && element.closest(".accordion-item") === section) {
      element.classList.add("case-study-mark");
      marked += 1;
    }
  }
  if (section && !marked) {
    section.classList.add("case-study-mark");
  }
}

// Scroll the container to the mark if the mark is out of view. The window is not moved.
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

// Scroll the panels sideways to the target, and call done at the end.
function slide(strip, target, done) {
  if (strip.sliding) {
    window.cancelAnimationFrame(strip.sliding);
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    done();
    return;
  }
  const start = strip.scrollLeft;
  const began = window.performance.now();
  function step(now) {
    const progress = Math.min((now - began) / 1000, 1);
    const eased = progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(-2 * progress + 2, 3) / 2;
    strip.scrollLeft = start + (target - start) * eased;
    if (progress < 1) {
      strip.sliding = window.requestAnimationFrame(step);
    } else {
      strip.sliding = null;
      done();
    }
  }
  strip.sliding = window.requestAnimationFrame(step);
}

// Draw the breadcrumbs, the process flow and the panels of the pages.
function draw(container, sliding) {
  const state = states.get(container);
  rememberOpen(container, state);
  const found = pages(state);
  const level = found.length - 1;
  let shown = container.querySelector(":scope > .case-study");
  if (!shown) {
    shown = make("div", "case-study");
    shown.append(make("nav"), make("div"), make("div", "case-study-strip overflow-x-hidden d-flex flex-row py-md-5 py-3"));
    container.replaceChildren(shown);
    // The panel in view is kept in view when the width changes.
    new ResizeObserver(function () {
      const strip = shown.lastElementChild;
      if (!strip.sliding) {
        strip.scrollLeft = (strip.children.length - 1) * strip.clientWidth;
      }
    }).observe(shown.lastElementChild);
  }
  shown.children[0].replaceWith(breadcrumbs(container, state, found));
  const flow = shown.children[1];
  const header = processFlow(container, state, found, flow.classList.contains("workflow-header") ? flow : null);
  if (header !== flow) {
    flow.replaceWith(header);
  }
  const strip = shown.lastElementChild;
  const panels = Array.from(strip.children);
  for (let at = 0; at <= level; at += 1) {
    const panel = make("div", "case-study-panel");
    panel.dataset.address = found[at]["@id"] || "";
    panel.append(view(container, state, found[at], at));
    if (panels[at]) {
      panels[at].replaceWith(panel);
    } else {
      strip.append(panel);
    }
  }
  const settle = function () {
    while (strip.children.length > level + 1) {
      strip.lastElementChild.remove();
    }
    strip.scrollLeft = level * strip.clientWidth;
  };
  if (sliding && Math.abs(strip.scrollLeft - level * strip.clientWidth) > 1) {
    slide(strip, level * strip.clientWidth, settle);
  } else {
    settle();
  }
  mark(container, state);
}

function navigate(container, path) {
  const state = states.get(container);
  state.path = path;
  draw(container, true);
  if (state.options.onNavigate) {
    state.options.onNavigate(state.path.length ? state.path[state.path.length - 1] : state.document["@id"]);
  }
}

// Draw the document of a case study in a container.
export function renderCaseStudy(container, caseStudy, options) {
  let state = states.get(container);
  if (!state) {
    containers += 1;
    state = { id: "case-study-" + containers, path: [], open: new Map() };
    states.set(container, state);
    // onPick is called after the action of the buttons of the page, such as the opening of another page. A click on
    // the icon for a new tab is not picked.
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
  // With arrive, draw the case study page first, then slide the requested page into place.
  if (state.options.arrive && state.path.length) {
    const path = state.path;
    state.path = [];
    draw(container, false);
    window.requestAnimationFrame(function () {
      state.path = path;
      draw(container, true);
    });
    return;
  }
  draw(container, false);
}

// Mark the elements of a field of the page at an address, and open that page.
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
