// The record editor: the form is built by shacl-form from the model's shapes and saved through the records
// API (Graph Store Protocol) with the record's version. The preview beside it shows what is published: the
// record's page, or its linked data.
import { busy } from "./busy.js";
import { current, outline, reveal as showPart, select, whenSelected } from "./record-index.js";

(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  // A record elsewhere, such as an ontology term, is under /api/ at its whole address.
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

  // Platform addresses are opened on this server, so they work on every copy.
  function pageLink(address) {
    return address.startsWith(editor.base) ? "/" + address.slice(editor.base.length) : address;
  }

  function show(text, ok) {
    message.className = "alert " + (ok ? "alert-success" : "alert-danger");
    message.textContent = text;
  }

  // A refusal is shown by *refuse*, else above the form.
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

  // The values that saving removes, by label path, from the preview.
  function removals(edges, trail, found) {
    for (const edge of edges) {
      if (edge.status === "removed") {
        found.push(trail + edge.label + ": " + (edge.name || edge.value || ""));
      }
      removals(edge.parts || [], trail + edge.label + " > ", found);
    }
    return found;
  }

  // The record's statements as a diagram: an arrow per value, green when added, red when removed. Parts
  // (sections, listed tools) have their own arrows.
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

  // The messages of each field are listed with the label of the field in the form, if it is known.
  function listMessages(id, messages, labels) {
    const list = document.getElementById(id);
    list.replaceChildren();
    for (const [field, found] of Object.entries(messages || {})) {
      list.append(make("li", "", ((labels || {})[field] || field) + ": " + found.join(" ")));
    }
    list.parentElement.classList.toggle("d-none", !list.children.length);
  }

  // What saving publishes, previewed without saving; only the latest answer is drawn. Until the form is
  // edited, the published record is shown, as shacl-form sends no change on load.
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

  // The case study's page (static/js/case-study.js): the published record, then each preview.
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

  // What is clicked in the case study's page is shown in the form: the part at the page's address, its
  // section by position and name, and the field, at the value clicked when there is one.
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

  // The focused field is marked on the page of the nearest node with an address. A node without one,
  // reached by schema:hasPart, is a section, known by position and name.
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
      return node.tagName === "SHACL-NODE" && !node.dataset.nodeId.startsWith("_:");
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

  // The statements of the form, as N-Triples. A new part with an address of its own, such as a new step, is
  // given a bare identifier by shacl-form (<8f2c-...>); it is written as a node without an address, which the
  // platform gives an address from its name. Nodes without an address are labelled with letters and digits
  // only, as jsonld reads them. A node stands first on a line (subject) or last before " ." (object); a text in
  // quotes is not changed.
  function label(given) {
    return "_:b" + given.replace(/[^A-Za-z0-9]/g, "");
  }

  // The identifier of a node of the form in the preview: its address, or its label as statements() writes it.
  function previewId(nodeId) {
    if (nodeId.startsWith("_:")) {
      return label(nodeId.slice(2));
    }
    return nodeId.includes(":") ? nodeId : label(nodeId);
  }

  function statements() {
    return form.serialize("application/n-quads")
      .replace(/^(?:<([^>:]*)>|_:(\S+)) /gm, function (all, bare, blank) { return label(bare || blank) + " "; })
      .replace(/ (?:<([^>:]*)>|_:(\S+)) \.$/gm, function (all, bare, blank) { return " " + label(bare || blank) + " ."; });
  }

  // The published case study gives the JSON-LD context and the names of the linked records.
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

  // The case study is drawn from the form in the browser, with no call to the platform. The statements of
  // the form are compacted with the context of the published case study, and the linked records keep the
  // names that the published case study gives.
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
    // A page added in the form is in the preview now, so the preview goes to the part being edited.
    if (current()) {
      markSelected(current());
    }
  }

  // Any other record's page is shown in a frame: the published page, or the one made from the form. Its
  // links open in a new tab, and its scroll is kept.
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
      // Not remembered where the browser keeps no storage.
    }
  }

  function recall(name) {
    try {
      return window.localStorage.getItem(name);
    } catch (error) {
      return null;
    }
  }

  // The preview is shown on its page or its linked data, or hidden. A record elsewhere, such as an ontology
  // term, has no page here.
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

  // A choice made with a click is remembered.
  function chooseByClick(next, shown) {
    choose(next, shown);
    remember("editor-preview", shown ? view : "hidden");
  }

  // The field being typed in is left, so that its value is taken, and the preview is drawn at once.
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

  // Records and sections share the side box on narrower screens.
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

  // A part shown in the form is shown in the preview: its page, or the section on the page that holds it.
  function markSelected(node) {
    if (!caseStudyComponent || !caseStudy) {
      return;
    }
    if (node.dataset.nodeId.startsWith("_:")) {
      const page = node.parentElement.closest("shacl-node:not([data-node-id^='_:'])");
      if (page) {
        caseStudyComponent.markField(caseStudy, previewId(page.dataset.nodeId), "", { position: valueOf(node, SCHEMA + "position"), name: valueOf(node, SCHEMA + "name") });
      }
    } else {
      caseStudyComponent.markField(caseStudy, previewId(node.dataset.nodeId), "", null);
    }
  }

  if (form) {
    // A change that leaves the record as loaded, such as an empty field drawn, is no edit.
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
    // Focus within the form reaches its shadow root, not the form.
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

  // The pressed button turns until the record reopens or the platform refuses.
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
    move: function (event) {
      const to = window.prompt("New address (the old one forwards to it):", path);
      if (to && to !== path) {
        act(event.currentTarget, "Moving…", "POST", "/api/move", JSON.stringify({ record: path, to: to }), editor.base + to);
      }
    },
  };
  for (const button of document.querySelectorAll("[data-action]")) {
    button.addEventListener("click", actions[button.dataset.action]);
  }
})();
