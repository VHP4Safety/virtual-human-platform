// The record's outline beside the form: its groups and the parts it holds, by name. An entry is opened and
// shown in the form when clicked; the entry in view is marked, and entries with values to fix get a dot.
const NAME = "https://schema.org/name";

function make(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className || "";
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

// A part's own name, not one of the parts it holds.
function nameOf(node) {
  for (const field of node.querySelectorAll('.property-instance[data-path="' + NAME + '"]')) {
    if (field.closest("shacl-node") === node) {
      const input = field.querySelector(".shown") || field.querySelector(".editor");
      return input ? String(input.value || "").trim() : "";
    }
  }
  return "";
}

// Groups of the record are entries; groups within parts are left out, and their contents lifted.
function entries(element, nested, found) {
  for (const child of element.children) {
    if (child.tagName === "SHACL-NODE") {
      const entry = { label: nameOf(child) || "Untitled", target: child, children: [], count: false };
      entries(child, true, entry.children);
      found.push(entry);
    } else if (child.tagName === "ROKIT-COLLAPSIBLE" && !(nested && child.hasAttribute("data-subject"))) {
      const entry = { label: child.label || "", target: child, children: [], count: !child.hasAttribute("data-subject") };
      entries(child, nested, entry.children);
      found.push(entry);
    } else {
      entries(child, nested, found);
    }
  }
  return found;
}

export function outline(form, nav) {
  // Whether each entry is open, by its trail of labels; deeper ones start closed.
  const opened = new Map();
  let shown = [];

  function reveal(target) {
    for (let node = target; node; node = node.parentElement) {
      if (node.tagName === "ROKIT-COLLAPSIBLE") {
        node.open = true;
      }
    }
    window.requestAnimationFrame(function () {
      target.scrollIntoView({ block: "start", behavior: "smooth" });
      // Its first field takes the focus, so the preview shows the same part.
      const first = target.querySelector(".property-instance .shown, .property-instance .editor:not([type=hidden])");
      if (first) {
        first.focus({ preventScroll: true });
      }
      target.classList.add("index-shown");
      window.setTimeout(function () { target.classList.remove("index-shown"); }, 1600);
    });
  }

  function draw(list, trail, depth) {
    const branch = make("ul", depth ? "record-index-branch" : "record-index-tree");
    for (const entry of list) {
      const key = trail + "/" + entry.label;
      const item = make("li");
      const row = make("div", "record-index-row");
      const toggle = make("button", "record-index-toggle");
      toggle.type = "button";
      const link = make("button", "record-index-link", entry.label);
      link.type = "button";
      link.title = entry.label;
      link.addEventListener("click", function () { reveal(entry.target); });
      row.append(toggle, link);
      if (entry.count && entry.children.length) {
        row.append(make("span", "record-index-count", String(entry.children.length)));
      }
      if (entry.target.querySelector(".property-instance.invalid")) {
        const dot = make("span", "record-index-problem");
        dot.title = "Values to fix";
        row.append(dot);
      }
      item.append(row);
      shown.push({ target: entry.target, row: row });
      if (entry.children.length) {
        const open = opened.has(key) ? opened.get(key) : depth < 2;
        const children = draw(entry.children, key, depth + 1);
        children.hidden = !open;
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", "Show or hide " + entry.label);
        toggle.addEventListener("click", function () {
          const opening = children.hidden;
          children.hidden = !opening;
          toggle.setAttribute("aria-expanded", String(opening));
          opened.set(key, opening);
        });
        item.append(children);
      } else {
        toggle.disabled = true;
      }
      branch.append(item);
    }
    return branch;
  }

  // The last entry whose place in the form is above the top of the window, among those drawn and open.
  function spy() {
    let current = null;
    for (const entry of shown) {
      const place = entry.target.getBoundingClientRect();
      if (place.height > 0 && place.top <= 120 && entry.row.offsetParent !== null) {
        current = entry;
      }
    }
    for (const entry of shown) {
      entry.row.classList.toggle("active", entry === current);
    }
  }

  function refresh() {
    const root = form.shadowRoot && form.shadowRoot.querySelector("shacl-node");
    if (!root) {
      return;
    }
    shown = [];
    const found = entries(root, false, []);
    nav.replaceChildren(found.length ? draw(found, "", 0) : make("p", "text-secondary mb-0", "No sections."));
    spy();
  }

  let timer = null;
  form.addEventListener("ready", refresh);
  form.addEventListener("change", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(refresh, 400);
  });
  let waiting = false;
  window.addEventListener("scroll", function () {
    if (!waiting) {
      waiting = true;
      window.requestAnimationFrame(function () {
        waiting = false;
        spy();
      });
    }
  }, { passive: true });
}
