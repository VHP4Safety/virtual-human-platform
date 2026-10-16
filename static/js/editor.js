// The record editor: the form is built by shacl-form from the model's shapes and saved through the records
// API (Graph Store Protocol) with the record's version. The linked data beside it shows what is published.
import { busy } from "./busy.js";

(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  // A record elsewhere, such as an ontology term, is under /api/ at its whole address.
  const path = editor.graph.startsWith(editor.base) ? editor.graph.slice(editor.base.length) : editor.graph;
  const graph = "/api/" + encodeURI(path).replace(/#/g, "%23");
  const form = document.querySelector("shacl-form");
  const column = document.getElementById("main-column");
  const showRdf = document.getElementById("show-rdf");
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

  // What blocks saving, next to Save: each field by its label path, with a Show button.
  function showProblems(answer) {
    const panel = document.getElementById("save-problems");
    const fields = Object.keys(answer.fields);
    panel.replaceChildren(make("div", "fw-semibold mb-1", "Not saved: " + fields.length + (fields.length === 1 ? " field to fix" : " fields to fix")));
    const list = make("ul", "mb-0 ps-3");
    for (const path of fields) {
      const item = make("li", "mb-1");
      item.append(make("span", "fw-semibold", (answer.labels && answer.labels[path]) || path), document.createTextNode(": " + answer.fields[path].join(" ") + " "));
      const button = make("button", "btn btn-link btn-sm p-0 align-baseline", "Show");
      button.type = "button";
      button.addEventListener("click", function () { reveal(path); });
      item.append(button);
      list.append(item);
    }
    panel.append(list);
    panel.classList.remove("d-none");
  }

  // The field's first flagged value, else its first value.
  function reveal(path) {
    const term = path.split(" > ").pop();
    const found = [];
    for (const instance of form.shadowRoot.querySelectorAll(".property-instance")) {
      if ((instance.dataset.path || "").split(/[/#]/).pop() === term) {
        found.push(instance);
      }
    }
    const flagged = found.find(function (instance) { return instance.classList.contains("invalid"); }) || found[0];
    if (flagged) {
      flagged.scrollIntoView({ block: "center", behavior: "smooth" });
    }
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

  function listMessages(id, messages) {
    const list = document.getElementById(id);
    list.replaceChildren();
    for (const [field, found] of Object.entries(messages || {})) {
      list.append(make("li", "", field + ": " + found.join(" ")));
    }
    list.parentElement.classList.toggle("d-none", !list.children.length);
  }

  // What saving publishes, previewed without saving; only the latest answer is drawn. Until the form is
  // edited, the published record is drawn, as shacl-form sends no change on load.
  let edited = false;

  // The case study's page under the form (static/js/case-study.js): the published record, then each preview.
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
      onNavigate: function () {
        caseStudy.scrollTop = 0;
      },
    });
    document.getElementById("case-study-caption").textContent = edited ? "Unsaved changes" : "As published";
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

  async function showPublishedCaseStudy() {
    const response = await fetch(graph, { credentials: "same-origin", headers: { Accept: "application/ld+json" } });
    if (response.ok && !edited) {
      showCaseStudy(await response.json());
    }
  }

  async function renderPreview() {
    if (!form || !(showRdf.checked || (caseStudy && edited))) {
      return;
    }
    document.getElementById("rdf-caption").textContent = "Checking…";
    let turtle = "";
    if (edited || !editor.version) {
      turtle = form.serialize("text/turtle");
    } else {
      turtle = await (await fetch(graph, { headers: { Accept: "text/turtle" } })).text();
    }
    if (previewRequest) {
      previewRequest.abort();
    }
    const request = new AbortController();
    previewRequest = request;
    let answer;
    try {
      const response = await fetch(graph + "?preview=true", {
        method: "PUT",
        credentials: "same-origin",
        signal: request.signal,
        headers: { "X-Form-Token": editor.token, "Content-Type": "text/turtle" },
        body: turtle,
      });
      answer = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        document.getElementById("rdf-caption").textContent = answer.message || "Linked data not built.";
        return;
      }
    } catch (error) {
      return;
    }
    if (previewRequest !== request) {
      return;
    }
    const added = answer.edges.filter(function (edge) { return edge.status === "added"; }).length;
    const removed = answer.edges.filter(function (edge) { return edge.status === "removed"; }).length;
    document.getElementById("rdf-caption").textContent = added || removed
      ? "On save: " + added + " added, " + removed + " removed"
      : "Nothing to save";
    renderGraph(document.getElementById("rdf-graph"), answer);
    listMessages("rdf-problems", answer.fields);
    listMessages("rdf-warnings", answer.warnings);
    showCaseStudy(answer.document);
  }

  function schedulePreview() {
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(renderPreview, 500);
  }

  function showPreview() {
    document.getElementById("rdf-column").classList.toggle("d-none", !showRdf.checked);
    document.getElementById("layout").classList.toggle("with-preview", showRdf.checked);
    try {
      window.localStorage.setItem("editor-show-rdf", showRdf.checked ? "yes" : "no");
    } catch (error) {
      // Not remembered where the browser keeps no storage.
    }
    schedulePreview();
  }

  try {
    showRdf.checked = window.localStorage.getItem("editor-show-rdf") === "yes";
  } catch (error) {
    showRdf.checked = false;
  }
  showRdf.addEventListener("change", showPreview);
  showPreview();

  if (caseStudy && editor.version) {
    showPublishedCaseStudy();
  }

  if (form) {
    form.addEventListener("change", function () {
      edited = true;
      schedulePreview();
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

    // Saving is decided by the platform's checks; unlike the form's checks, warnings do not block it.
    async function saved(turtle, working) {
      const preview = await send("PUT", graph + "?preview=true", turtle, "text/turtle", refuse);
      if (!preview) {
        return false;
      }
      if (Object.keys(preview.fields).length) {
        showProblems(preview);
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
      if (await saved(form.serialize("text/turtle"), working)) {
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

  const image = document.getElementById("image");
  if (image) {
    image.addEventListener("change", async function () {
      const body = new FormData();
      body.append("image", image.files[0]);
      const working = busy(image.parentElement, "Uploading…", column);
      const answer = await send("POST", "/api/images", body);
      working.done();
      if (answer) {
        show("Image address, for the image field: " + answer["@id"], true);
      }
    });
  }
})();
