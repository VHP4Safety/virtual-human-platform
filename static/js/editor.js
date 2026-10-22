// Record editor.
import { busy } from "./busy.js";
import { GLOSSARY, requestAddress, tableChoice } from "./glossary.js";
import { current, isPart, outline, reveal as showPart, select, whenSelected } from "./record-index.js";

(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  // A record outside the platform, such as an ontology term, is read at /api/ with its full address.
  const path = editor.graph.startsWith(editor.base) ? editor.graph.slice(editor.base.length) : editor.graph;
  const graph = "/api/" + encodeURI(path).replace(/#/g, "%23");
  const form = document.querySelector("shacl-form");
  const column = document.getElementById("main-column");
  const SCHEMA = "https://schema.org/";
  let previewTimer = null;
  let previewRequest = null;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    node.className = className || "";
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  // Open platform addresses on this server, so that the links are valid on each copy.
  function pageLink(address) {
    return address.startsWith(editor.base) ? "/" + address.slice(editor.base.length) : address;
  }

  function show(text, ok) {
    message.className = "alert " + (ok ? "alert-success" : "alert-danger");
    message.textContent = text;
  }

  // Send a request to the API. Show a refusal with refuse, else above the form.
  async function send(method, address, body, type, refuse) {
    const headers = { "X-Form-Token": editor.token };
    if (editor.version) {
      headers["If-Match"] = '"' + editor.version + '"';
    }
    if (type) {
      headers["Content-Type"] = type;
    }
    const refused = refuse || function (text) { show(text, false); };
    let response;
    try {
      response = await fetch(address, { method: method, credentials: "same-origin", headers: headers, body: body });
    } catch (error) {
      refused("No answer from the platform.");
      return null;
    }
    const answer = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const fields = Object.entries(answer.errors || {}).map(function (entry) { return entry[0] + ": " + entry[1].join(" "); });
      refused([answer.message || response.statusText].concat(fields).join(" "));
      return null;
    }
    return answer;
  }

  function reopen(address) {
    window.location.search = "?record=" + encodeURIComponent(address);
  }

  // Return the values removed by a save, by label path, from the preview.
  function removals(edges, trail, found) {
    for (const edge of edges) {
      if (edge.status === "removed") {
        found.push(trail + edge.label + ": " + (edge.name || edge.value || ""));
      }
      removals(edge.parts || [], trail + edge.label + " > ", found);
    }
    return found;
  }

  // Draw the statements of the record as a diagram of added, removed and kept values.
  function renderEdges(found) {
    const edges = make("ul", "graph-edges");
    for (const edge of found) {
      const item = make("li", "graph-edge graph-" + edge.status);
      const property = make("span", "graph-property", edge.label + " ");
      property.append(make("code", "small", edge.property));
      const value = make("span", "graph-value");
      if (edge.parts) {
        value.append(make("i", "bi bi-box text-secondary"), document.createTextNode(" " + edge.type + (edge.value ? ": " + edge.value : "")));
      } else if (edge.link) {
        const link = make("a", "link-vhpblue", edge.name || edge.value);
        link.href = pageLink(edge.value);
        value.append(link);
      } else {
        value.textContent = "“" + edge.value + "”";
      }
      item.append(property, make("i", "bi bi-arrow-right text-secondary"), value);
      if (edge.status !== "kept") {
        item.append(make("span", "badge " + (edge.status === "added" ? "text-bg-success" : "text-bg-danger"), edge.status));
      }
      if (edge.parts) {
        item.append(renderEdges(edge.parts));
      }
      edges.append(item);
    }
    return edges;
  }

  function renderGraph(box, found) {
    box.replaceChildren();
    const node = make("div", "graph-node");
    const record = make("a", "fw-semibold link-vhppurple", found.record_name);
    record.href = pageLink(found.record);
    node.append(make("i", "bi bi-box text-vhppurple"), record, make("span", "small text-secondary", found.type + " · " + pageLink(found.record)));
    box.append(node, renderEdges(found.edges));
  }

  // List the messages of each field with the label of the field in the form, if it is known.
  function listMessages(id, messages, labels) {
    const list = document.getElementById(id);
    list.replaceChildren();
    for (const [field, found] of Object.entries(messages || {})) {
      list.append(make("li", "", ((labels || {})[field] || field) + ": " + found.join(" ")));
    }
    list.parentElement.classList.toggle("d-none", !list.children.length);
  }

  // The preview of what a save publishes, made without a save. Only the latest response is drawn. Until the form is
  // edited, the published record is shown, as no change is sent by shacl-form on load.
  let edited = false;
  const panel = document.getElementById("preview-column");
  const caption = document.getElementById("preview-caption");
  const pageView = document.getElementById("page-view");
  const frame = document.getElementById("page-frame");
  let view = "page";

  function say(text, working) {
    caption.replaceChildren();
    if (working) {
      caption.append(make("span", "spinner-border spinner-border-sm me-1"));
    }
    caption.append(document.createTextNode(text));
  }

  // The page of the case study (static/js/case-study.js), drawn from the published record, then from each preview.
  const caseStudy = document.getElementById("case-study");
  let caseStudyComponent = null;

  async function showCaseStudy(found) {
    if (!caseStudy || !found) {
      return;
    }
    if (!caseStudyComponent) {
      caseStudyComponent = await import(caseStudy.dataset.component);
    }
    caseStudyComponent.renderCaseStudy(caseStudy, found, {
      base: editor.base,
      linkTarget: "_blank",
      openDisabled: true,
      // A page opened in the preview is shown in the form too.
      onNavigate: function (address) {
        pageView.scrollTop = 0;
        const node = Array.from(form.shadowRoot.querySelectorAll("shacl-node")).find(function (found) {
          return previewId(found.dataset.nodeId) === address;
        });
        if (node) {
          select(node);
        }
      },
      onPick: showEditing,
    });
  }

  // Show in the form what is clicked on the page of the case study.
  function showEditing(address, field, section, value) {
    const own = function (element, node) { return element.closest("shacl-node") === node; };
    let node = Array.from(form.shadowRoot.querySelectorAll("shacl-node")).find(function (found) {
      return found.dataset.nodeId === address;
    });
    if (!node) {
      return;
    }
    if (section) {
      let fit = 0;
      let found = null;
      for (const part of node.querySelectorAll('.property-instance[data-path="' + SCHEMA + 'hasPart"] > shacl-node')) {
        const fits = (parseFloat(valueOf(part, SCHEMA + "position")) === parseFloat(section.position) ? 2 : 0) + (valueOf(part, SCHEMA + "name") === section.name ? 1 : 0);
        if (own(part.parentElement, node) && fits > fit) {
          fit = fits;
          found = part;
        }
      }
      node = found || node;
    }
    let target = node;
    for (const name of field.split(" ").filter(Boolean)) {
      const fields = Array.from(node.querySelectorAll(".property-instance")).filter(function (instance) {
        return own(instance, node) && term(instance.dataset.path || "") === name;
      });
      const valued = fields.find(function (instance) {
        const input = instance.querySelector("input.editor");
        return value && input && (input.value === value || input.value === JSON.stringify(value));
      });
      if (valued || fields.length) {
        target = valued || fields[0];
        break;
      }
    }
    showPart(target);
  }

  // Mark the focused field on the page of the nearest node with an address.
  function term(path) {
    return path.split(/[/#]/).pop();
  }

  function valueOf(node, path) {
    const field = node.querySelector('.property-instance[data-path="' + path + '"]');
    const input = field && (field.querySelector(".shown") || field.querySelector(".editor"));
    return input ? input.value : "";
  }

  function markCaseStudy(event) {
    if (!caseStudyComponent) {
      return;
    }
    const found = event.composedPath().filter(function (node) {
      return node instanceof HTMLElement && (node.tagName === "SHACL-NODE" || node.classList.contains("property-instance"));
    });
    const at = found.findIndex(function (node) {
      return node.tagName === "SHACL-NODE" && !isPart(node.dataset.nodeId);
    });
    if (at < 1) {
      return;
    }
    const reached = found[at - 1].dataset.path;
    const part = found[at - 2];
    if (reached === SCHEMA + "hasPart" && part && part.tagName === "SHACL-NODE") {
      const section = { position: valueOf(part, SCHEMA + "position"), name: valueOf(part, SCHEMA + "name") };
      caseStudyComponent.markField(caseStudy, found[at].dataset.nodeId, at > 2 ? term(found[0].dataset.path) : "", section);
    } else {
      caseStudyComponent.markField(caseStudy, found[at].dataset.nodeId, term(reached), null);
    }
  }

  // Return a node label of letters and digits only, as jsonld requires.
  function label(given) {
    return "_:b" + given.replace(/[^A-Za-z0-9]/g, "");
  }

  // Return the identifier of a node of the form in the preview.
  function previewId(nodeId) {
    if (nodeId.startsWith("_:")) {
      return label(nodeId.slice(2));
    }
    return nodeId.includes(":") ? nodeId : label(nodeId);
  }

  // Return the statements of the form as N-Triples, with new parts as nodes without an address.
  function statements() {
    return form.serialize("application/n-quads")
      .replace(/^(?:<([^>:]*)>|_:(\S+)) /gm, function (all, bare, blank) { return label(bare || blank) + " "; })
      .replace(/ (?:<([^>:]*)>|_:(\S+)) \.$/gm, function (all, bare, blank) { return " " + label(bare || blank) + " ."; });
  }

  // The published case study, for the JSON-LD context and the names of the linked records.
  let published = null;

  async function showPublishedCaseStudy() {
    const response = await fetch(graph, { credentials: "same-origin", headers: { Accept: "application/ld+json" } });
    if (response.ok) {
      published = await response.json();
      if (!edited) {
        showCaseStudy(published);
      }
    }
  }

  // Draw the case study from the form in the browser.
  async function showLiveCaseStudy() {
    if (!published) {
      await showPublishedCaseStudy();
    }
    const flat = await jsonld.compact(await jsonld.fromRDF(statements(), { format: "application/n-quads" }), published["@context"]);
    const nodes = flat["@graph"] || [flat];
    const root = nodes.find(function (node) { return node["@id"] === editor.graph; });
    if (!root) {
      return;
    }
    const rest = nodes.filter(function (node) { return node !== root; });
    await showCaseStudy(Object.assign({}, root, { "@context": published["@context"], "@included": rest.concat([published]) }));
    // A page added in the form is now in the preview, so go to the part that is edited.
    if (current()) {
      markSelected(current());
    }
  }

  // Show the page of a record in a frame.
  function showPage(html) {
    const top = frame.contentWindow ? frame.contentWindow.scrollY : 0;
    frame.addEventListener("load", function () {
      const base = frame.contentDocument.createElement("base");
      base.target = "_blank";
      frame.contentDocument.head.prepend(base);
      frame.contentWindow.scrollTo(0, top);
    }, { once: true });
    if (html === null) {
      frame.removeAttribute("srcdoc");
      frame.src = pageLink(editor.graph);
    } else {
      frame.srcdoc = html;
    }
  }

  async function renderPreview() {
    if (!form || !panel || panel.classList.contains("d-none")) {
      return;
    }
    // A case study is drawn in the browser, from the form, at once.
    if (view === "page" && caseStudy) {
      say(edited ? "With unsaved changes" : "As published");
      showLiveCaseStudy();
      return;
    }
    if (view === "page" && !edited && editor.version) {
      say("As published");
      if (caseStudy) {
        showPublishedCaseStudy();
      } else if (frame.hasAttribute("srcdoc") || !frame.getAttribute("src")) {
        showPage(null);
      }
      return;
    }
    say(view === "page" ? "Making the page…" : "Checking…", true);
    let turtle = "";
    if (edited || !editor.version) {
      turtle = statements();
    } else {
      turtle = await (await fetch(graph, { headers: { Accept: "text/turtle" } })).text();
    }
    if (previewRequest) {
      previewRequest.abort();
    }
    const request = new AbortController();
    previewRequest = request;
    const page = view === "page" && !caseStudy;
    let response;
    try {
      response = await fetch(graph + "?preview=true" + (page ? "&page=true" : ""), {
        method: "PUT",
        credentials: "same-origin",
        signal: request.signal,
        headers: { "X-Form-Token": editor.token, "Content-Type": "text/turtle" },
        body: turtle,
      });
    } catch (error) {
      if (previewRequest === request) {
        say("No answer from the platform.");
      }
      return;
    }
    if (previewRequest !== request) {
      return;
    }
    if (page && response.headers.get("Content-Type").startsWith("text/html")) {
      say(response.ok ? "With unsaved changes" : "Page not found");
      showPage(await response.text());
      return;
    }
    const answer = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      say(answer.message || "Preview not made.");
      return;
    }
    if (view === "page") {
      say("With unsaved changes");
      showCaseStudy(answer.document);
      return;
    }
    const added = answer.edges.filter(function (edge) { return edge.status === "added"; }).length;
    const removed = answer.edges.filter(function (edge) { return edge.status === "removed"; }).length;
    say(added || removed ? "On save: " + added + " added, " + removed + " removed" : "Nothing to save");
    renderGraph(document.getElementById("rdf-graph"), answer);
    listMessages("rdf-problems", answer.fields, answer.labels);
    listMessages("rdf-warnings", answer.warnings, answer.labels);
  }

  function schedulePreview() {
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(renderPreview, caseStudy && view === "page" ? 150 : 500);
  }

  function remember(name, value) {
    try {
      window.localStorage.setItem(name, value);
    } catch (error) {
      // The choice is not remembered if the browser has no storage.
    }
  }

  function recall(name) {
    try {
      return window.localStorage.getItem(name);
    } catch (error) {
      return null;
    }
  }

  // Show or hide the preview of the page or of the linked data.
  function choose(next, shown) {
    view = panel.querySelector("[data-view=page]").disabled ? "data" : next;
    panel.classList.toggle("d-none", !shown);
    document.getElementById("show-preview").classList.toggle("d-none", shown);
    document.getElementById("layout").classList.toggle("with-preview", shown);
    for (const button of panel.querySelectorAll("[data-view]")) {
      button.classList.toggle("active", button.dataset.view === view);
      button.setAttribute("aria-selected", String(button.dataset.view === view));
    }
    pageView.classList.toggle("d-none", view !== "page");
    document.getElementById("rdf-view").classList.toggle("d-none", view !== "data");
    schedulePreview();
  }

  // Remember a choice made with a click.
  function chooseByClick(next, shown) {
    choose(next, shown);
    remember("editor-preview", shown ? view : "hidden");
  }

  // Leave the field that is typed in, so that its value is taken, and draw the preview at once.
  function updateView() {
    let typing = form ? form.shadowRoot.activeElement : null;
    while (typing && typing.shadowRoot && typing.shadowRoot.activeElement) {
      typing = typing.shadowRoot.activeElement;
    }
    if (typing) {
      typing.blur();
    }
    window.clearTimeout(previewTimer);
    window.setTimeout(renderPreview, 50);
  }

  if (panel) {
    document.getElementById("update-preview").addEventListener("click", updateView);
    for (const button of panel.querySelectorAll("[data-view]")) {
      button.addEventListener("click", function () { chooseByClick(button.dataset.view, true); });
    }
    document.getElementById("hide-preview").addEventListener("click", function () { chooseByClick(view, false); });
    document.getElementById("show-preview").addEventListener("click", function () { chooseByClick(view, true); });
    const kept = recall("editor-preview");
    choose(kept === "data" ? "data" : "page", kept !== "hidden");
  }

  // On narrow screens, the records and the sections are in one side box.
  const side = document.getElementById("side");
  for (const tab of side.querySelectorAll(".editor-side-tabs [data-pane]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.pane === side.dataset.pane));
    tab.addEventListener("click", function () {
      side.dataset.pane = tab.dataset.pane;
      for (const other of side.querySelectorAll(".editor-side-tabs [data-pane]")) {
        other.setAttribute("aria-selected", String(other === tab));
      }
    });
  }

  if (form) {
    outline(form, document.getElementById("record-index"));
    whenSelected(markSelected);
  }

  // Mark the part that is shown in the form in the preview.
  function markSelected(node) {
    if (!caseStudyComponent || !caseStudy) {
      return;
    }
    if (isPart(node.dataset.nodeId)) {
      let page = node.parentElement.closest("shacl-node");
      while (page && isPart(page.dataset.nodeId)) {
        page = page.parentElement.closest("shacl-node");
      }
      if (page) {
        caseStudyComponent.markField(caseStudy, previewId(page.dataset.nodeId), "", { position: valueOf(node, SCHEMA + "position"), name: valueOf(node, SCHEMA + "name") });
      }
    } else {
      caseStudyComponent.markField(caseStudy, previewId(node.dataset.nodeId), "", null);
    }
  }

  // A record that is kept as it is in the editor, such as a model, has no Save.
  if (form && document.getElementById("save")) {
    // A change after which the record is as loaded, such as a new empty field, is not an edit.
    let loaded = null;
    form.addEventListener("ready", function () {
      loaded = form.serialize("text/turtle");
    });
    const discard = document.getElementById("discard");
    form.addEventListener("change", function () {
      edited = loaded !== null && form.serialize("text/turtle") !== loaded;
      discard.classList.toggle("d-none", !edited);
      schedulePreview();
    });
    // While a field is typed in, its value is taken after a short pause, so the preview follows the typing.
    let typingTimer = null;
    form.addEventListener("input", function () {
      window.clearTimeout(typingTimer);
      typingTimer = window.setTimeout(function () {
        let typing = form.shadowRoot.activeElement;
        while (typing && typing.shadowRoot && typing.shadowRoot.activeElement && !typing.classList.contains("editor")) {
          typing = typing.shadowRoot.activeElement;
        }
        if (typing) {
          typing.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
        }
      }, 600);
    });
    discard.addEventListener("click", function () {
      if (window.confirm("Discard the changes? The record is opened again as it was saved.")) {
        busy(discard, "Discarding…", column);
        reopen(editor.graph);
      }
    });
    // Focus events within the form are sent to its shadow root, not to the form.
    if (caseStudy) {
      form.addEventListener("focusin", function (event) {
        form.shadowRoot.addEventListener("focusin", markCaseStudy);
        markCaseStudy(event);
      }, { once: true });
    }
    const save = document.getElementById("save");
    const problems = document.getElementById("save-problems");
    function refuse(text) {
      problems.replaceChildren(make("div", "", "Not saved: " + text));
      problems.classList.remove("d-none");
    }

    // Values that do not fit the model are saved, and shown as warnings; only removals are confirmed.
    async function saved(turtle, working) {
      const preview = await send("PUT", graph + "?preview=true", turtle, "text/turtle", refuse);
      if (!preview) {
        return false;
      }
      // Removals are confirmed first.
      if (editor.version) {
        const gone = removals(preview.edges, "", []);
        const listed = gone.slice(0, 15).join("\n") + (gone.length > 15 ? "\n…" : "");
        if (gone.length && !window.confirm("Saving removes:\n\n" + listed + "\n\nSave anyway?")) {
          return false;
        }
      }
      working.say("Saving…");
      return Boolean(await send("PUT", graph, turtle, "text/turtle", refuse));
    }

    // Save is enabled once the form has loaded; an empty form would remove every value.
    form.addEventListener("ready", function () {
      save.disabled = false;
    });
    save.addEventListener("click", async function () {
      problems.classList.add("d-none");
      const working = busy(save, "Checking…", column);
      if (await saved(statements(), working)) {
        working.say("Saved; reloading…");
        reopen(editor.graph);
      } else {
        working.done();
      }
    });
  }

  // Send a change. The pressed button turns until the record is opened again or the request is refused.
  async function act(button, text, method, address, body, reopened) {
    const working = busy(button, text, column);
    if (await send(method, address, body, body ? "application/json" : undefined)) {
      reopen(reopened);
    } else {
      working.done();
    }
  }

  const actions = {
    remove: function (event) {
      if (window.confirm("Remove this record? Its address then answers 410 Gone.")) {
        act(event.currentTarget, "Removing…", "DELETE", graph, undefined, editor.graph);
      }
    },
    restore: function (event) {
      act(event.currentTarget, "Restoring…", "POST", "/api/restore", JSON.stringify({ record: path }), editor.graph);
    },
    // A draft term of the glossary is requested with the term request form of the glossary, filled in with its values.
    // The tab is opened at the click, as browsers block tabs opened after a wait.
    request: async function () {
      const tab = window.open("", "_blank");
      tab.opener = null;
      try {
        const term = await (await fetch(graph, { headers: { Accept: "application/ld+json" } })).json();
        const references = [].concat(term["http://www.w3.org/2000/01/rdf-schema#isDefinedBy"] || []).map(function (given) { return given["@id"] || given; });
        const definition = term.description && term.description["@value"] !== undefined ? term.description["@value"] : term.description;
        tab.location = requestAddress({ name: term.name, abbreviation: [].concat(term.alternateName || [])[0], definition: definition, references: references,
                                        address: editor.graph }, document.getElementById("term-table").value);
      } catch (error) {
        tab.close();
        throw error;
      }
    },
    // An imported model is saved unchanged, so that it is a platform record, with a draft RO-Crate.
    own: function () {
      if (window.confirm("Make this model a platform record? Imports from Zenodo then leave it unchanged, and its RO-Crate is a draft made from the record.")) {
        document.getElementById("save").click();
      }
    },
    move: function (event) {
      const to = window.prompt("New address (the old one forwards to it):", path);
      if (to && to !== path) {
        act(event.currentTarget, "Moving…", "POST", "/api/move", JSON.stringify({ record: path, to: to }), editor.base + to);
      }
    },
  };
  // The request of a draft term is offered for the glossary, with a choice of its table.
  const requesting = document.getElementById("term-request");
  if (requesting && editor.draftVocabulary === GLOSSARY) {
    const table = tableChoice();
    table.id = "term-table";
    table.classList.add("w-auto");
    requesting.querySelector("label").after(table);
    requesting.classList.replace("d-none", "d-inline-flex");
  }
  for (const button of document.querySelectorAll("[data-action]")) {
    button.addEventListener("click", actions[button.dataset.action]);
  }
})();
