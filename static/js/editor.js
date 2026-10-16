// The record editor: shacl-form builds the form from the model's shapes, and each change is sent to the
// records API (the W3C Graph Store Protocol), with the editor's login and the record's version. Beside the
// form, the linked data shows the statements that saving would publish.
(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  // A record elsewhere, such as a term of an ontology, is at its whole address under /api/.
  const path = editor.graph.startsWith(editor.base) ? editor.graph.slice(editor.base.length) : editor.graph;
  const graph = "/api/" + encodeURI(path).replace(/#/g, "%23");
  const form = document.querySelector("shacl-form");
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

  // A platform address is shown from this server, so that it works on every copy of the platform.
  function pageLink(address) {
    return address.startsWith(editor.base) ? "/" + address.slice(editor.base.length) : address;
  }

  function show(text, ok) {
    message.className = "alert " + (ok ? "alert-success" : "alert-danger");
    message.textContent = text;
  }

  async function send(method, address, body, type) {
    const headers = { "X-Form-Token": editor.token };
    if (editor.version) {
      headers["If-Match"] = '"' + editor.version + '"';
    }
    if (type) {
      headers["Content-Type"] = type;
    }
    const response = await fetch(address, { method: method, credentials: "same-origin", headers: headers, body: body });
    const answer = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const fields = Object.entries(answer.errors || {}).map(function (entry) { return entry[0] + ": " + entry[1].join(" "); });
      show([answer.message || response.statusText].concat(fields).join(" "), false);
      return null;
    }
    return answer;
  }

  function reopen(address) {
    window.location.search = "?record=" + encodeURIComponent(address);
  }

  // What keeps the record from being saved, next to the Save button: each field once, by the names of the
  // fields that lead to it, with what is wrong and a button that shows it in the form.
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

  // The first value of a field in the form that its checks flag, else the first value of the field.
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

  // The values that saving removes, by the fields that lead to them, as the platform's preview tells them.
  function removals(edges, trail, found) {
    for (const edge of edges) {
      if (edge.status === "removed") {
        found.push(trail + edge.label + ": " + (edge.name || edge.value || ""));
      }
      removals(edge.parts || [], trail + edge.label + " > ", found);
    }
    return found;
  }

  // The record's statements as a diagram: an arrow from the record to each value, green when saving adds
  // it, red when saving removes it. A part of the record (a section, a listed tool) has its own arrows.
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

  // The preview asks the platform what saving would publish, without saving anything; only the latest
  // request is drawn. Until the record is edited, it is drawn from the record as it is published, as
  // shacl-form tells nothing when it has loaded the record.
  let edited = false;

  // A case study's page as the website will show it, in the panel under the form (static/js/case-study.js):
  // drawn from the record as it is published, then from each preview of the form's changes.
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
    document.getElementById("case-study-caption").textContent = edited ? "With the form's changes, not saved yet" : "As published";
  }

  // The field that the form is on is marked in the case study's page, on the page of the nearest node of the
  // form that has an address. A node without one, reached from that page by its sections (schema:hasPart),
  // is a section, known by its position and name.
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
        document.getElementById("rdf-caption").textContent = answer.message || "The linked data could not be built.";
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
      ? "When you save: " + added + " added, " + removed + " removed"
      : "As published; nothing to save";
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
      // The choice is not remembered where the browser keeps no storage.
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
    // The focus that moves within the form reaches its shadow root, not the form itself.
    if (caseStudy) {
      form.addEventListener("focusin", function (event) {
        form.shadowRoot.addEventListener("focusin", markCaseStudy);
        markCaseStudy(event);
      }, { once: true });
    }
    // The platform's checks decide whether a record is saved: a value that is only recommended does not
    // keep it from being saved, as the form's own checks would.
    document.getElementById("save").addEventListener("click", async function () {
      const turtle = form.serialize("text/turtle");
      document.getElementById("save-problems").classList.add("d-none");
      const preview = await send("PUT", graph + "?preview=true", turtle, "text/turtle");
      if (!preview) {
        return;
      }
      if (Object.keys(preview.fields).length) {
        showProblems(preview);
        return;
      }
      // A save that removes values asks first, so that no value is removed that the editor did not mean to.
      if (editor.version) {
        const gone = removals(preview.edges, "", []);
        const listed = gone.slice(0, 15).join("\n") + (gone.length > 15 ? "\n…" : "");
        if (gone.length && !window.confirm("Saving removes:\n\n" + listed + "\n\nSave anyway?")) {
          return;
        }
      }
      if (await send("PUT", graph, turtle, "text/turtle")) {
        reopen(editor.graph);
      }
    });
  }

  const actions = {
    remove: async function () {
      if (window.confirm("Remove this record? Its address answers 410 Gone from then on.") && await send("DELETE", graph)) {
        reopen(editor.graph);
      }
    },
    restore: async function () {
      if (await send("POST", "/api/restore", JSON.stringify({ record: path }), "application/json")) {
        reopen(editor.graph);
      }
    },
    move: async function () {
      const to = window.prompt("The record's new address; the old one will forward to it.", path);
      if (to && to !== path && await send("POST", "/api/move", JSON.stringify({ record: path, to: to }), "application/json")) {
        reopen(editor.base + to);
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
      const answer = await send("POST", "/api/images", body);
      if (answer) {
        show("The image's address, to give in the image field: " + answer["@id"], true);
      }
    });
  }
})();
