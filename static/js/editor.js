// The record editor: shacl-form builds the form from the model's shapes, and each change is sent to the
// records API (the W3C Graph Store Protocol), with the editor's login and the record's version.
(function () {
  const editor = JSON.parse(document.getElementById("editor").textContent);
  const message = document.getElementById("message");
  const graph = "/api/records?graph=" + encodeURIComponent(editor.graph);

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

  // The record's linked data, as the form will send it.
  const form = document.querySelector("shacl-form");
  const turtle = document.getElementById("turtle");
  if (form) {
    form.addEventListener("change", function () {
      turtle.textContent = form.serialize("text/turtle");
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
