/**
 * The record editor. The server makes the form from the platform's model; this script fills it with a
 * record, sends it to the write API with the editor's login (the session, and its form token in the
 * X-Form-Token header), and shows the answer: the record saved, or what is wrong with each field.
 */
(function () {
  const data = JSON.parse(document.getElementById("editor-data").textContent);
  const form = document.getElementById("record-form");
  const start = document.getElementById("start");
  const identifier = document.getElementById("identifier");
  const list = document.getElementById("record-list");
  const showRdf = document.getElementById("show-rdf");
  const one = data.kind.endsWith("s") ? data.kind.slice(0, -1) : data.kind;
  const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
  let previewTimer = null;
  let previewRequest = null;
  let selected = null;
  let identifierTouched = false;
  let unsaved = false;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function isWebAddress(text) {
    return text.startsWith("https://") || text.startsWith("http://");
  }

  // A platform address is shown from this server, so that it works on every copy of the platform.
  function pageLink(address) {
    return address.startsWith(data.base) ? "/" + address.slice(data.base.length) : address;
  }

  function fieldInput(name) {
    return form.querySelector('[data-field="' + name + '"]');
  }

  function slug(text) {
    return text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  }

  function toast(text, ok, link) {
    const box = document.getElementById("toast");
    box.className = "toast align-items-center border-0 " + (ok ? "text-bg-success" : "text-bg-danger");
    const body = document.getElementById("toast-text");
    body.textContent = text;
    if (link) {
      const anchor = make("a", "link-light fw-semibold ms-1", link.text);
      anchor.href = link.href;
      anchor.target = "_blank";
      anchor.rel = "noopener";
      body.append(anchor);
    }
    bootstrap.Toast.getOrCreateInstance(box).show();
  }

  function setUnsaved(value) {
    unsaved = value;
    document.getElementById("unsaved").classList.toggle("d-none", !value);
  }

  // Problems with the values

  function clearProblems() {
    document.getElementById("form-problem").classList.add("d-none");
    for (const box of form.querySelectorAll("[data-problem]")) {
      box.classList.add("d-none");
      box.textContent = "";
    }
    for (const marked of form.querySelectorAll(".is-invalid")) {
      marked.classList.remove("is-invalid");
    }
  }

  function showProblem(name, text) {
    const box = form.querySelector('[data-problem="' + name + '"]');
    if (!box) {
      return null;
    }
    box.textContent = text;
    box.classList.remove("d-none");
    const field = name === "identifier" ? identifier : fieldInput(name);
    if (field && field.type !== "hidden") {
      field.classList.add("is-invalid");
    }
    return box;
  }

  function showProblems(fields, general) {
    clearProblems();
    let first = null;
    for (const name of Object.keys(fields)) {
      first = showProblem(name, fields[name].join(" ")) || first;
    }
    if (first) {
      first.closest("[data-field-box]").scrollIntoView({ behavior: "smooth", block: "center" });
    } else if (general) {
      const problem = document.getElementById("form-problem");
      problem.textContent = general;
      problem.classList.remove("d-none");
      problem.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  // The checks the browser can make before sending; the platform checks everything again.
  function problemsBeforeSending() {
    const problems = {};
    for (const field of data.fields) {
      const input = fieldInput(field.name);
      if (!input || input.type === "hidden") {
        continue;
      }
      const text = input.value.trim();
      if (field.required && !text) {
        problems[field.name] = [field.message || "This field is required."];
      } else if (text && field.pattern && !new RegExp(field.pattern).test(text)) {
        problems[field.name] = [field.message || "This value does not have the expected form."];
      } else if (text && field.entry === "address" && !isWebAddress(text)) {
        problems[field.name] = ["Write the full address, starting with https:// (or http://)."];
      }
    }
    if (identifier.value && !/^[a-z0-9][a-z0-9-]*$/.test(identifier.value)) {
      problems.identifier = ["Use lowercase letters, digits and hyphens only."];
    }
    return problems;
  }

  async function api(method, address, body, version) {
    const options = { method: method, credentials: "same-origin", headers: { "X-Form-Token": form.dataset.formToken } };
    if (version) {
      options.headers["If-Match"] = '"' + version + '"';
    }
    if (body instanceof FormData) {
      options.body = body;
    } else if (body) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    const response = await fetch(address, options);
    const answer = await response.json().catch(function () { return { error: response.statusText }; });
    return { ok: response.ok, status: response.status, answer: answer };
  }

  // How complete a record is: the fields that have a value, of those an editor fills in

  function editable() {
    return data.fields.filter(function (field) { return field.entry !== "fixed"; });
  }

  function isFilled(value) {
    return Array.isArray(value) ? value.length > 0 : Boolean(value);
  }

  function renderCompleteness() {
    const box = document.getElementById("completeness");
    const body = values();
    const missing = [];
    for (const field of editable()) {
      const filled = isFilled(body[field.name]);
      const mark = form.querySelector('[data-missing="' + field.name + '"]');
      if (mark) {
        mark.classList.toggle("d-none", filled);
      }
      if (!filled) {
        missing.push(field);
      }
    }
    box.replaceChildren();
    const total = editable().length;
    const done = total - missing.length;
    const bar = make("div", "progress mb-1");
    bar.style.height = "6px";
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-label", "Fields filled in");
    bar.setAttribute("aria-valuenow", String(done));
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", String(total));
    const fill = make("div", "progress-bar " + (missing.length ? "bg-vhporange" : "bg-success"));
    fill.style.width = Math.round(100 * done / total) + "%";
    bar.append(fill);
    const line = make("div", "text-secondary", done + " of " + total + " fields filled in");
    if (missing.length) {
      line.append(". Missing: ");
      missing.forEach(function (field, position) {
        const jump = make("a", "link-vhpblue", field.label);
        jump.href = "#";
        jump.addEventListener("click", function (event) {
          event.preventDefault();
          const target = form.querySelector('[data-field-box="' + field.name + '"]');
          target.scrollIntoView({ behavior: "smooth", block: "center" });
          const entry = target.querySelector("input:not([type=hidden]):not([type=file]), textarea, button");
          if (entry) {
            entry.focus({ preventScroll: true });
          }
        });
        line.append(jump, position < missing.length - 1 ? ", " : "");
      });
    }
    box.append(bar, line);
  }

  function completenessOf(record) {
    let done = 0;
    for (const field of editable()) {
      if (isFilled(record.values[field.name])) {
        done += 1;
      }
    }
    return done;
  }

  // The list of records

  function renderCounts() {
    let listed = 0;
    let edited = 0;
    let removed = 0;
    for (const record of data.records) {
      if (record.removed) {
        removed += 1;
      } else {
        listed += 1;
        if (record.edited) {
          edited += 1;
        }
      }
    }
    document.getElementById("counts").textContent = listed + " in the catalogue · " + edited + " edited on the platform · " + removed + " removed";
  }

  function renderList() {
    renderCounts();
    const filter = document.getElementById("filter").value.trim().toLowerCase();
    const show = document.querySelector('input[name="show"]:checked').value;
    list.replaceChildren();
    for (const record of data.records) {
      const name = record.values.name || record.identifier;
      if (filter && !name.toLowerCase().includes(filter) && !record.identifier.includes(filter)) {
        continue;
      }
      if ((show === "edited" && !(record.edited && !record.removed)) || (show === "removed" && !record.removed)) {
        continue;
      }
      const item = make("button", "list-group-item list-group-item-action d-flex align-items-center gap-2" + (record === selected ? " active bg-vhpblue border-vhpblue" : ""));
      item.type = "button";
      const label = make("span", "flex-grow-1 text-truncate", name);
      label.title = name;
      item.append(label);
      if (record.removed) {
        item.append(make("span", "badge text-bg-secondary", "removed"));
      } else {
        if (record.edited) {
          item.append(make("span", "badge text-bg-vhplight-blue", "edited"));
        }
        const done = completenessOf(record);
        const total = editable().length;
        const count = make("span", "small " + (done === total ? "text-success" : "text-secondary"), done === total ? "\u2713" : done + "/" + total);
        count.title = done + " of " + total + " fields filled in";
        item.append(count);
      }
      item.addEventListener("click", function () { open(record); });
      list.append(item);
    }
    if (!list.children.length) {
      list.append(make("div", "small text-secondary p-2", "No " + data.kind + " match."));
    }
  }

  // The fields that link to things: one checkbox for each record they can link to

  function renderChoices(field, values, disabled) {
    const box = form.querySelector('[data-choices="' + field.name + '"]');
    box.replaceChildren();
    const known = new Set();
    const groups = (data.choices[field.name] || []).slice();
    let count = 0;
    for (const group of groups) {
      for (const option of group.options) {
        known.add(option.iri);
      }
    }
    const others = values.filter(function (value) { return !known.has(value); });
    if (others.length) {
      groups.push({ title: "Other links", options: others.map(function (value) { return { iri: value, name: value, description: "" }; }) });
    }
    const single = field.entry === "choice";
    if (single) {
      groups.push({ title: "", options: [{ iri: "", name: "Not given", description: "" }] });
    }
    let total = 0;
    for (const group of groups) {
      total += group.options.length;
    }
    // A long list gets a box that narrows it down by name.
    if (total > 12) {
      const finder = make("input", "form-control form-control-sm");
      finder.type = "search";
      finder.placeholder = "Find in this list";
      finder.setAttribute("aria-label", "Find in the list of " + field.label);
      finder.addEventListener("input", function () {
        const text = finder.value.trim().toLowerCase();
        for (const check of box.querySelectorAll(".form-check")) {
          check.classList.toggle("d-none", Boolean(text) && !check.textContent.toLowerCase().includes(text));
        }
      });
      const holder = make("div", "col-12");
      holder.append(finder);
      box.append(holder);
    }
    for (const group of groups) {
      const column = make("div", single ? "col-12" : "col-md-6");
      if (group.title) {
        column.append(make("div", "small fw-semibold text-secondary mb-1", group.title));
      }
      for (const option of group.options) {
        count += 1;
        const id = "choice-" + field.name + "-" + count;
        const check = make("div", single ? "form-check form-check-inline mb-1" : "form-check mb-1");
        const input = make("input", "form-check-input");
        input.type = single ? "radio" : "checkbox";
        input.name = "choice-" + field.name;
        input.id = id;
        input.value = option.iri;
        input.checked = option.iri ? values.includes(option.iri) : (single && values.length === 0);
        input.disabled = disabled;
        input.dataset.choiceOf = field.name;
        const label = make("label", "form-check-label", option.name);
        label.htmlFor = id;
        if (option.description) {
          const description = make("span", "small text-secondary choice-description", option.description);
          description.title = option.description;
          label.append(description);
        }
        check.append(input, label);
        column.append(check);
      }
      box.append(column);
    }
  }

  function chosen(name) {
    const values = [];
    for (const input of form.querySelectorAll('[data-choice-of="' + name + '"]')) {
      if (input.checked && input.value) {
        values.push(input.value);
      }
    }
    return values;
  }

  // The fields that take pages with their titles

  function addDetail(name, address, title, disabled) {
    const box = form.querySelector('[data-details="' + name + '"]');
    const row = make("div", "input-group");
    const titleInput = make("input", "form-control");
    titleInput.placeholder = "Title";
    titleInput.value = title || "";
    titleInput.disabled = disabled;
    titleInput.dataset.titleOf = name;
    titleInput.setAttribute("aria-label", "Title");
    const addressInput = make("input", "form-control");
    addressInput.type = "url";
    addressInput.placeholder = "https://";
    addressInput.value = address || "";
    addressInput.disabled = disabled;
    addressInput.dataset.detailOf = name;
    addressInput.setAttribute("aria-label", "Address");
    const remove = make("button", "btn btn-outline-secondary");
    remove.type = "button";
    remove.disabled = disabled;
    remove.setAttribute("aria-label", "Remove this page");
    remove.append(make("i", "bi bi-x-lg"));
    remove.addEventListener("click", function () {
      row.remove();
      setUnsaved(true);
      renderCompleteness();
      schedulePreview();
    });
    row.append(titleInput, addressInput, remove);
    box.append(row);
    return titleInput;
  }

  function renderDetails(field, values, disabled) {
    form.querySelector('[data-details="' + field.name + '"]').replaceChildren();
    for (const address of values) {
      addDetail(field.name, address, data.names[address] || "", disabled);
    }
    form.querySelector('[data-add-detail="' + field.name + '"]').disabled = disabled;
  }

  function details(name) {
    const found = [];
    for (const input of form.querySelectorAll('[data-detail-of="' + name + '"]')) {
      const address = input.value.trim();
      if (address) {
        const title = input.parentElement.querySelector('[data-title-of="' + name + '"]').value.trim();
        found.push(title ? { "@id": address, name: title } : { "@id": address });
      }
    }
    return found;
  }

  // A DOI is looked up at doi.org, so that the editor sees which publication it names.

  async function lookUp(name) {
    const box = form.querySelector('[data-lookup="' + name + '"]');
    if (!box) {
      return;
    }
    const address = fieldInput(name).value.trim();
    box.classList.add("d-none");
    if (!/^https:\/\/doi\.org\/10\.\S+$/.test(address)) {
      return;
    }
    box.className = "form-text";
    box.textContent = "Looking up the DOI…";
    try {
      const response = await fetch(address, { headers: { Accept: "application/vnd.citationstyles.csl+json" } });
      if (fieldInput(name).value.trim() !== address) {
        return;
      }
      if (!response.ok) {
        box.className = "form-text text-danger";
        box.textContent = "No publication was found with this DOI. Check it before saving.";
        return;
      }
      const found = await response.json();
      const year = found.issued && found.issued["date-parts"] ? found.issued["date-parts"][0][0] : "";
      const parts = [found["container-title"], year].filter(function (part) { return part; });
      box.className = "form-text text-success";
      box.replaceChildren(make("i", "bi bi-check-circle"), " " + (found.title || "Publication found") + (parts.length ? " · " + parts.join(", ") : ""));
    } catch (error) {
      box.className = "form-text";
      box.textContent = "The DOI could not be looked up now; it is checked for its form when saving.";
    }
  }

  // The fields that take a list of web addresses

  function addAddress(name, value, disabled) {
    const box = form.querySelector('[data-addresses="' + name + '"]');
    const row = make("div", "input-group");
    const input = make("input", "form-control");
    input.type = "url";
    input.inputMode = "url";
    input.placeholder = "https://";
    input.value = value || "";
    input.disabled = disabled;
    input.dataset.addressOf = name;
    const remove = make("button", "btn btn-outline-secondary");
    remove.type = "button";
    remove.disabled = disabled;
    remove.setAttribute("aria-label", "Remove this address");
    remove.append(make("i", "bi bi-x-lg"));
    remove.addEventListener("click", function () {
      row.remove();
      setUnsaved(true);
      renderCompleteness();
      schedulePreview();
    });
    row.append(input, remove);
    box.append(row);
    return input;
  }

  function renderAddresses(field, values, disabled) {
    form.querySelector('[data-addresses="' + field.name + '"]').replaceChildren();
    for (const value of values) {
      addAddress(field.name, value, disabled);
    }
    form.querySelector('[data-add-address="' + field.name + '"]').disabled = disabled;
  }

  function addresses(name) {
    const found = [];
    for (const input of form.querySelectorAll('[data-address-of="' + name + '"]')) {
      if (input.value.trim()) {
        found.push(input.value.trim());
      }
    }
    return found;
  }

  // The fields that take an image

  function setImage(name, address) {
    fieldInput(name).value = address;
    const preview = form.querySelector('[data-preview="' + name + '"]');
    const shown = isWebAddress(address);
    preview.classList.toggle("d-none", !shown);
    form.querySelector('[data-no-image="' + name + '"]').classList.toggle("d-none", shown);
    form.querySelector('[data-clear="' + name + '"]').classList.toggle("d-none", !address);
    form.querySelector('[data-choose="' + name + '"] span').textContent = address ? "Replace the image" : "Upload an image";
    if (shown) {
      preview.src = pageLink(address);
    } else {
      preview.removeAttribute("src");
    }
  }

  async function upload(name, file) {
    if (file.size > MAX_IMAGE_BYTES) {
      showProblem(name, "The image is larger than 5 MB.");
      return;
    }
    const payload = new FormData();
    payload.append("image", file);
    const button = form.querySelector('[data-choose="' + name + '"]');
    button.disabled = true;
    const result = await api("POST", "/api/images", payload);
    button.disabled = false;
    if (!result.ok) {
      showProblem(name, result.answer.error || "The image could not be uploaded.");
      return;
    }
    form.querySelector('[data-problem="' + name + '"]').classList.add("d-none");
    setImage(name, result.answer["@id"]);
    setUnsaved(true);
  }

  // The form

  function open(record) {
    if (unsaved && !window.confirm("Leave without saving your changes?")) {
      return;
    }
    selected = record;
    clearPreview("Building the linked data…");
    identifierTouched = false;
    start.classList.add("d-none");
    form.classList.remove("d-none");
    clearProblems();
    const removed = Boolean(record && record.removed);
    document.getElementById("form-title").textContent = record ? (record.values.name || record.identifier) : "New " + one;
    const badges = document.getElementById("form-badges");
    badges.replaceChildren();
    let note = "Fields marked * are required.";
    if (removed) {
      badges.append(make("span", "badge text-bg-secondary", "removed"));
      note = "This " + one + " was removed. Its page says so, and its address is not used again.";
    } else if (record && !record.edited) {
      badges.append(make("span", "badge text-bg-light border", "from the catalogue import"));
      note = "This " + one + " comes from the nightly import. Once you save it here, the platform's version is kept and the import no longer changes it.";
    }
    document.getElementById("form-note").textContent = note;
    identifier.value = record ? record.identifier : "";
    identifier.readOnly = Boolean(record);
    document.getElementById("identifier-change").classList.toggle("d-none", !record || removed);
    document.getElementById("identifier-help").classList.toggle("d-none", Boolean(record));
    for (const field of data.fields) {
      const value = record ? record.values[field.name] : null;
      if (field.entry === "links" || field.entry === "choice") {
        renderChoices(field, Array.isArray(value) ? value : (value ? [value] : []), removed);
      } else if (field.entry === "details") {
        renderDetails(field, Array.isArray(value) ? value : [], removed);
      } else if (field.entry === "addresses") {
        renderAddresses(field, Array.isArray(value) ? value : [], removed);
      } else if (field.entry === "image") {
        setImage(field.name, value || "");
        for (const button of form.querySelectorAll('[data-choose="' + field.name + '"], [data-clear="' + field.name + '"]')) {
          button.disabled = removed;
        }
      } else if (field.entry !== "fixed") {
        fieldInput(field.name).value = Array.isArray(value) ? value.join(" ") : (value || "");
        fieldInput(field.name).disabled = removed;
        lookUp(field.name);
      }
    }
    document.getElementById("save").disabled = removed;
    document.getElementById("remove").classList.toggle("d-none", !record);
    document.getElementById("remove").disabled = false;
    document.getElementById("restore").classList.toggle("d-none", !removed);
    document.getElementById("removal-keep").disabled = removed;
    document.getElementById("removal-keep").checked = !removed;
    document.getElementById("removal-free").checked = removed;
    const view = document.getElementById("view");
    view.classList.toggle("d-none", !record || removed);
    view.href = record ? "/" + data.kind + "/" + record.identifier : "#";
    const history = document.getElementById("history");
    history.classList.toggle("d-none", !record);
    history.href = record ? "/changes?record=" + encodeURIComponent(data.base + data.kind + "/" + record.identifier) : "#";
    setUnsaved(false);
    renderList();
    renderCompleteness();
    loadSaved();
    if (!record) {
      fieldInput(data.fields[0].name).focus();
    }
  }

  function close() {
    if (unsaved && !window.confirm("Leave without saving your changes?")) {
      return;
    }
    setUnsaved(false);
    selected = null;
    form.classList.add("d-none");
    start.classList.remove("d-none");
    renderList();
  }

  function values() {
    const body = {};
    for (const field of data.fields) {
      if (field.entry === "fixed") {
        continue;
      }
      if (field.entry === "links" || field.entry === "choice") {
        const links = chosen(field.name);
        if (links.length) {
          body[field.name] = field.entry === "choice" ? links[0] : links;
        }
        continue;
      }
      if (field.entry === "details") {
        const pages = details(field.name);
        if (pages.length) {
          body[field.name] = pages;
        }
        continue;
      }
      if (field.entry === "addresses") {
        const found = addresses(field.name);
        if (found.length) {
          body[field.name] = found;
        }
        continue;
      }
      const text = fieldInput(field.name).value.trim();
      if (text) {
        body[field.name] = text;
      }
    }
    return body;
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const problems = problemsBeforeSending();
    if (Object.keys(problems).length) {
      showProblems(problems);
      return;
    }
    const body = values();
    const address = identifier.value.trim();
    const save = document.getElementById("save");
    save.disabled = true;
    const result = address
      ? await api("PUT", "/api/" + data.kind + "/" + encodeURIComponent(address), body, selected ? selected.version : null)
      : await api("POST", "/api/" + data.kind, body);
    save.disabled = false;
    if (!result.ok) {
      if (result.status === 412) {
        showProblems({}, result.answer.error);
      } else if (result.status === 409) {
        showProblems({ identifier: ["This address belonged to a removed " + one + ". Choose another one."] });
      } else {
        showProblems(result.answer.fields || {}, result.answer.error || "The " + one + " could not be saved.");
      }
      return;
    }
    const saved = result.answer["@id"].split("/").pop();
    let record = null;
    for (const known of data.records) {
      if (known.identifier === saved) {
        record = known;
      }
    }
    if (!record) {
      record = { identifier: saved };
      data.records.unshift(record);
    }
    record.values = body;
    for (const field of data.fields) {
      if (field.entry === "details" && Array.isArray(body[field.name])) {
        record.values[field.name] = body[field.name].map(function (page) {
          data.names[page["@id"]] = page.name || data.names[page["@id"]] || "";
          return page["@id"];
        });
      }
    }
    record.edited = true;
    record.removed = false;
    record.version = result.answer.version;
    setUnsaved(false);
    open(record);
    const repeated = Object.keys(result.answer.warnings || {}).length > 0;
    toast(repeated
      ? "Saved. Another " + one + " has the same name or website; check that this is not a duplicate."
      : "Saved. The " + one + "'s page shows it now.", true, { text: "See the change", href: result.answer.change });
  });

  async function remove() {
    const permanently = document.getElementById("removal-free").checked;
    const record = selected;
    const name = record.values.name || record.identifier;
    const result = await api("DELETE", "/api/" + data.kind + "/" + encodeURIComponent(record.identifier) + (permanently ? "?permanent=true" : ""), null, record.version);
    bootstrap.Modal.getOrCreateInstance(document.getElementById("remove-dialog")).hide();
    if (!result.ok) {
      toast(result.answer.error || "The " + one + " could not be removed.", false);
      return;
    }
    setUnsaved(false);
    if (permanently) {
      data.records.splice(data.records.indexOf(record), 1);
      close();
    } else {
      record.removed = true;
      record.edited = true;
      record.version = result.answer.version;
      open(record);
    }
    toast("Removed " + name + ".", true, { text: "See the change", href: result.answer.change });
  }

  // The linked data of each change, for developers: a diagram of the record's statements

  function renderGraph(box, graph) {
    box.replaceChildren();
    const node = make("div", "graph-node");
    const record = make("a", "fw-semibold link-vhppurple", graph.record_name);
    record.href = pageLink(graph.record);
    record.target = "_blank";
    record.rel = "noopener";
    node.append(make("i", "bi bi-box text-vhppurple"), record, make("span", "small text-secondary", graph.type + " · " + pageLink(graph.record)));
    const edges = make("ul", "graph-edges");
    for (const edge of graph.edges) {
      const item = make("li", "graph-edge graph-" + edge.status);
      const property = make("span", "graph-property", edge.label + " ");
      property.append(make("code", "small", edge.property));
      const value = make("span", "graph-value");
      if (edge.link && isWebAddress(edge.value)) {
        const link = make("a", "link-vhpblue", edge.name || edge.value);
        link.href = pageLink(edge.value);
        link.title = edge.value;
        link.target = "_blank";
        link.rel = "noopener";
        value.append(link);
        if (edge.name) {
          value.append(" ", make("span", "small text-secondary text-break", edge.value));
        }
      } else {
        value.textContent = "\u201c" + edge.value + "\u201d";
      }
      item.append(property, make("i", "bi bi-arrow-right text-secondary"), value);
      if (edge.status !== "kept") {
        item.append(make("span", "badge " + (edge.status === "added" ? "text-bg-success" : "text-bg-danger"), edge.status));
      }
      edges.append(item);
    }
    box.append(node, edges);
  }

  // The preview asks the platform what saving would publish: it builds the record with rdfsolve and
  // checks it against the application profile, without saving anything.
  function clearPreview(text) {
    document.getElementById("rdf-caption").textContent = text;
    document.getElementById("rdf-graph").replaceChildren();
    document.getElementById("rdf-problems").parentElement.classList.add("d-none");
    document.getElementById("rdf-warnings").parentElement.classList.add("d-none");
  }

  async function renderPreview() {
    if (!showRdf.checked || form.classList.contains("d-none")) {
      return;
    }
    // Only the latest request is drawn: an earlier one is stopped, so that its answer never shows the
    // linked data of another record.
    if (previewRequest) {
      previewRequest.abort();
    }
    const request = new AbortController();
    previewRequest = request;
    const address = identifier.value.trim() || (selected ? selected.identifier : "");
    if (!address) {
      clearPreview("Fill in the name to see the linked data.");
      return;
    }
    let result;
    try {
      const response = await fetch("/api/" + data.kind + "/" + encodeURIComponent(address) + "?preview=true", {
        method: "PUT",
        credentials: "same-origin",
        signal: request.signal,
        headers: { "X-Form-Token": form.dataset.formToken, "Content-Type": "application/json" },
        body: JSON.stringify(values()),
      });
      result = { ok: response.ok, answer: await response.json().catch(function () { return {}; }) };
    } catch (error) {
      return;
    }
    if (previewRequest !== request) {
      return;
    }
    if (!result.ok) {
      clearPreview(result.answer.error || "The linked data could not be built.");
      return;
    }
    const graph = result.answer;
    const added = graph.edges.filter(function (edge) { return edge.status === "added"; }).length;
    const removed = graph.edges.filter(function (edge) { return edge.status === "removed"; }).length;
    caption.textContent = added || removed
      ? "When you save: " + added + " added, " + removed + " removed"
      : (selected ? "As published; nothing to save" : "Nothing to publish yet");
    renderGraph(document.getElementById("rdf-graph"), graph);
    const problems = document.getElementById("rdf-problems");
    problems.replaceChildren();
    for (const field of data.fields) {
      for (const message of (graph.fields || {})[field.name] || []) {
        problems.append(make("li", "", field.label + ": " + message));
      }
    }
    problems.parentElement.classList.toggle("d-none", !problems.children.length);
    const warnings = document.getElementById("rdf-warnings");
    warnings.replaceChildren();
    for (const field of data.fields) {
      for (const message of (graph.warnings || {})[field.name] || []) {
        warnings.append(make("li", "", field.label + ": " + message));
      }
    }
    warnings.parentElement.classList.toggle("d-none", !warnings.children.length);
  }

  function schedulePreview() {
    window.clearTimeout(previewTimer);
    previewTimer = window.setTimeout(renderPreview, 500);
  }

  function loadSaved() {
    const raw = document.getElementById("rdf-raw");
    raw.classList.toggle("d-none", !selected || selected.removed);
    if (selected && !selected.removed) {
      raw.href = "/" + data.kind + "/" + encodeURIComponent(selected.identifier) + ".ttl";
    }
    renderPreview();
  }

  function showPreview() {
    const shown = showRdf.checked;
    document.getElementById("rdf-column").classList.toggle("d-none", !shown);
    document.getElementById("layout").classList.toggle("with-preview", shown);
    if (shown) {
      loadSaved();
    }
  }

  // Wiring

  form.addEventListener("input", function (event) {
    setUnsaved(true);
    renderCompleteness();
    schedulePreview();
    if (event.target === identifier) {
      identifierTouched = true;
    }
    if (!selected && !identifierTouched && event.target === fieldInput("name")) {
      identifier.value = slug(event.target.value);
    }
  });
  form.addEventListener("change", function (event) {
    if (event.target.dataset.choiceOf) {
      setUnsaved(true);
    }
    renderCompleteness();
    schedulePreview();
  });
  for (const field of data.fields) {
    if (field.entry === "address") {
      fieldInput(field.name).addEventListener("change", function () { lookUp(field.name); });
    }
    if (field.entry === "image") {
      const chooser = form.querySelector('[data-upload="' + field.name + '"]');
      form.querySelector('[data-choose="' + field.name + '"]').addEventListener("click", function () { chooser.click(); });
      chooser.addEventListener("change", function () {
        if (chooser.files.length) {
          upload(field.name, chooser.files[0]);
        }
        chooser.value = "";
      });
      form.querySelector('[data-clear="' + field.name + '"]').addEventListener("click", function () {
        setImage(field.name, "");
        setUnsaved(true);
      });
    }
  }
  for (const field of data.fields) {
    if (field.entry === "details") {
      form.querySelector('[data-add-detail="' + field.name + '"]').addEventListener("click", function () {
        addDetail(field.name, "", "", false).focus();
      });
    }
    if (field.entry === "addresses") {
      form.querySelector('[data-add-address="' + field.name + '"]').addEventListener("click", function () {
        addAddress(field.name, "", false).focus();
      });
    }
  }

  // Changing a record's address: the old one forwards to the new one.
  document.getElementById("identifier-change").addEventListener("click", function () {
    document.getElementById("move-to").value = selected.identifier;
    document.getElementById("move-problem").classList.add("d-none");
    bootstrap.Modal.getOrCreateInstance(document.getElementById("move-dialog")).show();
  });
  document.getElementById("move-confirm").addEventListener("click", async function () {
    const to = document.getElementById("move-to").value.trim();
    const problem = document.getElementById("move-problem");
    if (!/^[a-z0-9][a-z0-9-]*$/.test(to) || to === selected.identifier) {
      problem.textContent = "Give a new address with lowercase letters, digits and hyphens.";
      problem.classList.remove("d-none");
      return;
    }
    const record = selected;
    const old = data.base + data.kind + "/" + record.identifier;
    const result = await api("POST", "/api/" + data.kind + "/" + encodeURIComponent(record.identifier) + "/move", { to: to }, record.version);
    if (!result.ok) {
      problem.textContent = result.answer.error || "The address could not be changed.";
      problem.classList.remove("d-none");
      return;
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById("move-dialog")).hide();
    record.identifier = to;
    record.version = result.answer.version;
    const others = (record.values.same_as || []).filter(function (value) { return value !== result.answer["@id"]; });
    if (!others.includes(old)) {
      others.push(old);
    }
    record.values.same_as = others;
    setUnsaved(false);
    open(record);
    toast("The address changed; the old one forwards here.", true, { text: "See the change", href: result.answer.change });
  });

  for (const button of document.querySelectorAll("[data-new]")) {
    button.addEventListener("click", function () { open(null); });
  }
  document.getElementById("discard").addEventListener("click", function () {
    if (selected) {
      setUnsaved(false);
      open(selected);
    } else {
      close();
    }
  });
  document.getElementById("remove").addEventListener("click", function () {
    bootstrap.Modal.getOrCreateInstance(document.getElementById("remove-dialog")).show();
  });
  document.getElementById("remove-confirm").addEventListener("click", remove);
  document.getElementById("restore").addEventListener("click", async function () {
    const record = selected;
    const result = await api("POST", "/api/" + data.kind + "/" + encodeURIComponent(record.identifier) + "/restore");
    if (!result.ok) {
      toast(result.answer.error || "The " + one + " could not be restored.", false);
      return;
    }
    record.removed = false;
    record.version = result.answer.version;
    open(record);
    toast("Restored " + (record.values.name || record.identifier) + ".", true, { text: "See the change", href: result.answer.change });
  });
  document.getElementById("filter").addEventListener("input", renderList);
  for (const choice of document.querySelectorAll('input[name="show"]')) {
    choice.addEventListener("change", renderList);
  }
  try {
    showRdf.checked = window.localStorage.getItem("editor-show-rdf") === "yes";
  } catch (error) {
    showRdf.checked = false;
  }
  showPreview();
  showRdf.addEventListener("change", function () {
    try {
      window.localStorage.setItem("editor-show-rdf", showRdf.checked ? "yes" : "no");
    } catch (error) {
      // Without storage, the choice lasts until the page is left.
    }
    showPreview();
  });
  window.addEventListener("beforeunload", function (event) {
    if (unsaved) {
      event.preventDefault();
    }
  });
  renderList();
})();
