// The record editor: shacl-form builds the form from the model's shapes, and each change is sent to the
// records API (the W3C Graph Store Protocol), with the editor's login and the record's version. Beside the
// form, the linked data shows the statements that saving would publish.
(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  const graph = "/api/records?graph=" + encodeURIComponent(editor.graph);
  const form = document.querySelector("shacl-form");
  const showRdf = document.getElementById("show-rdf");
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

  // The record's statements as a diagram: an arrow from the record to each value, green when saving adds
  // it, red when saving removes it.
  function renderGraph(box, found) {
    box.replaceChildren();
    const node = make("div", "graph-node");
    const record = make("a", "fw-semibold link-vhppurple", found.record_name);
    record.href = pageLink(found.record);
    node.append(make("i", "bi bi-box text-vhppurple"), record, make("span", "small text-secondary", found.type + " · " + pageLink(found.record)));
    const edges = make("ul", "graph-edges");
    for (const edge of found.edges) {
      const item = make("li", "graph-edge graph-" + edge.status);
      const property = make("span", "graph-property", edge.label + " ");
      property.append(make("code", "small", edge.property));
      const value = make("span", "graph-value");
      if (edge.link) {
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
      edges.append(item);
    }
    box.append(node, edges);
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

  async function renderPreview() {
    if (!showRdf.checked || !form) {
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
      const response = await fetch(graph + "&preview=true", {
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

  if (form) {
    form.addEventListener("change", function () {
      edited = true;
      schedulePreview();
    });
    form.addEventListener("submit", async function () {
      if (await send("PUT", graph, form.serialize("text/turtle"), "text/turtle")) {
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
      if (await send("POST", "/api/records/restore?graph=" + encodeURIComponent(editor.graph))) {
        reopen(editor.graph);
      }
    },
    move: async function () {
      const to = window.prompt("The record's new address; the old one will forward to it.", editor.graph);
      if (to && to !== editor.graph && await send("POST", "/api/records/move?graph=" + encodeURIComponent(editor.graph), JSON.stringify({ to: to }), "application/json")) {
        reopen(to);
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
