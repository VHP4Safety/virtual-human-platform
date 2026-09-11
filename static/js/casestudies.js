// casestudies.js
// JavaScript for Individual Case Study pages

// --- State management ---
let currentStep1Value = "";
let currentStep2Value = "";
let currentStep3Value = "";
let currentStep4Value = "";
let currentStep5Value = "";
let currentStep6Value = "";

// --- Content storage ---
let step1Contents = {};
let step2Contents = {};
let step3Contents = {};
let step4Contents = {};
let step5Contents = {};
let step6Contents = {};

let contentLoaded = false;

function stepTypeToColor(type) {
  baseclass = "btn text-white"
  color = "btn-vhpblue" 
  if (type == "workflow step" || type == "workflow-step") {
    color = "btn-vhpdarkteal"
  } else if (type == "workflow substep" || type == "workflow-substep") {
    color = "btn-vhplightteal"
  } else if (type == "process flow step" || type == "process-flow-step") {
    color = "btn-vhpdarkpurple"
  } else if (type == "regulatory question" || type == "regulatory-question") {
    color = "btn-vhppink-distinct"
  } else if (type == "tool") {
    color = "btn-vhpblue"
  } else {
    console.log("UNKNOWN STEP TYPE: " + type)
  }
  return baseclass + " " + color
}

// Headline accent color per step — matches the process-flow icon colors
// defined in casestudies.css (.step-item[data-step="N"] .step-icon).
function stepHeadingClass(stepNumber) {
  const map = {
    1: "text-vhppink-distinct",
    2: "text-vhpdarkpurple",
    3: "text-vhpdarkteal",
    4: "text-vhplightteal",
    5: "text-vhpblue",
    6: "text-vhplightteal",
  };
  return map[stepNumber] || "text-vhppink-distinct";
}

function stepAction(step, onClickFn) {
  if (step.type && step.type == "tool") {
    if (step.id) {
      const route = step.route || "tools"; // updated so that assays in methods can be linked too
      const url = "/" + route + "/" + step.id;
      return "onclick=\"location.href='" + url + "';\""
    } else {
      return ""
    }
  }

  if (step.type && step.type == "data") {
    if (step.id) {
      const route = step.route || "data";
      const url = "/" + route + "/" + step.id;
      return "onclick=\"location.href='" + url + "';\""
    } else {
      return ""
    }
  }

  if (onClickFn) {
    return "onclick=\"" + onClickFn + "('" + step.value + "')\""
  }

  return ""
}

// Helper to render step buttons from array
function renderStepButtons(steps, btnClass, onClickFn) {
  return (
    `<div class="row py-3">` +
    steps
      .map(
        (step) =>
        `
        <div class="col-md pb-2 d-flex align-items-stretch">
          <button class="btn w-100 text-white ${ stepTypeToColor(step.type) }${
            step.state && step.state == "disabled" ? " disabled opacity-25" : ""
          }"${ stepAction(step, onClickFn) }${
            step.state && step.state == "disabled" ? " disabled" : ""
          }><b>${step.label}</b>${
            step.description ? "<br />" + step.description : ""
          }</button>
          </div>
          `
      )
      .join("") +
    `</div>`
  );
}

// --- Content update functions ---
function updateStep1Content() {
  if (!contentLoaded) return;
  document.getElementById("step1-content").innerHTML =
    `<h1 class="${stepHeadingClass(1)}">${step1Contents.navTitle}</h1><p class="text-secondary fs-5">${step1Contents.navDescription}</p>` +
    renderStepButtons(step1Contents.questions, "step1", "selectStep1");
  document.getElementById("step1-bottom-content").innerHTML =
    buildAccordionHTML(step1Contents.content);
}
function updateStep2Content() {
  if (!contentLoaded) return;
  if (!step2Contents[currentStep1Value]) return;
  const nav = step2Contents[currentStep1Value];
  document.getElementById("step2-content").innerHTML =
  `<h1 class="${stepHeadingClass(2)}">${nav.navTitle}</h1>
   <p class="text-secondary fs-5">${nav.navDescription}</p>` +
    (nav.image ? nav.image : "") +             
  renderStepButtons(nav.steps, "step2", "selectStep2");
  document.getElementById("step2-bottom-content").innerHTML = buildAccordionHTML(nav.content);
}
function updateStep3Content() {
  if (!contentLoaded) return;
  if (!step3Contents[currentStep1Value]) return;
  const step = step3Contents[currentStep1Value][currentStep2Value];
  if (!step3Contents[currentStep1Value][currentStep2Value]) return;
  if (step.steps) {
    document.getElementById("step3-content").innerHTML =
      `<h1 class="${stepHeadingClass(3)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.steps, "step3", "selectStep3");
  } else if (step.tools) {
    document.getElementById("step3-content").innerHTML =
      `<h1 class="${stepHeadingClass(3)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.tools, "step3", null);
  }
  document.getElementById("step3-bottom-content").innerHTML = buildAccordionHTML(step.content);
}
function updateStep4Content() {
  if (!contentLoaded) return;
  if (!step4Contents) return;
  if (!step4Contents[currentStep1Value]) return;
  if (!step4Contents[currentStep1Value][currentStep2Value]) return;
  if (!step4Contents[currentStep1Value][currentStep2Value][currentStep3Value]) return;
  const step = step4Contents[currentStep1Value][currentStep2Value][currentStep3Value];
  if (step.tools) {
    document.getElementById("step4-content").innerHTML =
      `<h1 class="${stepHeadingClass(4)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.tools, "step4", null);
  } else if (step.steps) {
    document.getElementById("step4-content").innerHTML =
      `<h1 class="${stepHeadingClass(4)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.steps, "step4", "selectStep4");
  } else {
    document.getElementById("step4-content").innerHTML =
      `<h1 class="${stepHeadingClass(4)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>`;
  }
  document.getElementById("step4-bottom-content").innerHTML = buildAccordionHTML(step.content);
}
function updateStep5Content() {
  if (!contentLoaded) return;
  if (!step5Contents) return;
  if (!step5Contents[currentStep1Value]) return;
  if (!step5Contents[currentStep1Value][currentStep2Value]) return;
  if (!step5Contents[currentStep1Value][currentStep2Value][currentStep3Value]) return;
  if (!step5Contents[currentStep1Value][currentStep2Value][currentStep3Value][currentStep4Value]) return;
  const step = step5Contents[currentStep1Value][currentStep2Value][currentStep3Value][currentStep4Value];
  if (step.tools) {
    document.getElementById("step5-content").innerHTML =
      `<h1 class="${stepHeadingClass(5)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.tools, "step5", null);
  } else if (step.steps) {
    document.getElementById("step5-content").innerHTML =
      `<h1 class="${stepHeadingClass(5)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.steps, "step5", "selectStep5");
  } else {
    document.getElementById("step5-content").innerHTML =
      `<h1 class="${stepHeadingClass(5)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>`;
  }
  document.getElementById("step5-bottom-content").innerHTML = buildAccordionHTML(step.content);
}
function updateStep6Content() {
  if (!contentLoaded) return;
  if (!step6Contents) return;
  if (!step6Contents[currentStep1Value]) return;
  if (!step6Contents[currentStep1Value][currentStep2Value]) return;
  if (!step6Contents[currentStep1Value][currentStep2Value][currentStep3Value]) return;
  if (!step6Contents[currentStep1Value][currentStep2Value][currentStep3Value][currentStep4Value]) return;
  if (!step6Contents[currentStep1Value][currentStep2Value][currentStep3Value][currentStep4Value][currentStep5Value]) return;
  const step = step6Contents[currentStep1Value][currentStep2Value][currentStep3Value][currentStep4Value][currentStep5Value];
  if (step.tools) {
    document.getElementById("step6-content").innerHTML =
      `<h1 class="${stepHeadingClass(6)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.tools, "step6", null);
  } else if (step.steps) {
    document.getElementById("step6-content").innerHTML =
      `<h1 class="${stepHeadingClass(6)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>` +
      renderStepButtons(step.steps);
  } else {
    document.getElementById("step6-content").innerHTML =
      `<h1 class="${stepHeadingClass(6)}"><span class='kinetics-bold'>${step.navTitle}</span></h1><p class='step-desc text-secondary fs-5'>${step.navDescription}</p>`;
  }
  document.getElementById("step6-bottom-content").innerHTML = buildAccordionHTML(step.content);
}

// --- Navigation logic ---
function selectStep1(q) {
  currentStep1Value = q;
  currentStep2Value = "";
  currentStep3Value = "";
  updateStep2Content();
  updateStep3Content();
  updateStep4Content();
  updateStep5Content();
  updateStep6Content();
  goToStep(2);
}
function selectStep2(step) {
  currentStep2Value = step;
  updateStep3Content();
  goToStep(3);
}
function selectStep3(step) {
  currentStep3Value = step;
  updateStep4Content();
  goToStep(4);
}
function selectStep4(step) {
  currentStep4Value = step;
  updateStep5Content();
  goToStep(5);
}
function selectStep5(step) {
  currentStep5Value = step;
  updateStep6Content();
  goToStep(6);
}

// Breadcrumb logic
toTitleCase = (str) => str.charAt(0).toUpperCase() + str.slice(1);

function getCaseStudyNameFromUrl() {
  // Assumes URL like /casestudies/<casestudy>
  const path = window.location.pathname;
  // Try to extract the case study name from the path
  // e.g. /casestudies/kidney or /casestudies/thyroid
  const match = path.match(/\/casestudies\/(thyroid|kidney|parkinson)/);
  if (match && match[1]) {
    return match[1];
  }
  // fallback: try query param ?case=xxx
  const params = new URLSearchParams(window.location.search);
  if (params.has("case")) {
    return params.get("case");
  }
  
}

function getCaseStudyVersionFromUrl() {
  // Assumes URL like /casestudies/<casestudy>
  const params = new URLSearchParams(window.location.search);
  if (params.has("casestudybranch")) {
    return "refs/heads/" + params.get("casestudybranch");
  } else if (params.has("casestudycommit")) {
    return params.get("casestudycommit");
  }
  // fallback: default
  return "main";
}

function loadCaseStudyContent() {
  console.log("Loading case study content...")
  step = applyStateFromUrl();
  initWorkflowHeaderClicks();
  updateWorkflowHeader(step);
  const caseStudy = getCaseStudyNameFromUrl();
  const caseStudyBranch = getCaseStudyVersionFromUrl();
  var data_url = `https://raw.githubusercontent.com/VHP4Safety/ui-casestudy-config/${caseStudyBranch}/${caseStudy}_content.json`;
  //var data_url_test = `https://raw.githubusercontent.com/johannehouweling/ui-casestudy-config/refs/heads/jh-content-structure/${caseStudy}_content.json`
  fetch(data_url)
    .then((res) => res.json())
    .then((content) => {
      step1Contents = content.step1Contents;
      step2Contents = content.step2Contents;
      step3Contents = content.step3Contents;
      step4Contents = content.step4Contents;
      step5Contents = content.step5Contents;
      step6Contents = content.step6Contents;
      contentLoaded = true;
      updateStep1Content();
      step = applyStateFromUrl(); // re-read now the config keys are known
      updateStep2Content();
      updateStep3Content();
      updateStep4Content();
      updateStep5Content();
      updateStep6Content();
    });
}

function getCaseStudyDisplayName() {
  // Optionally, you could add a mapping here for pretty names
  const name = getCaseStudyNameFromUrl();
  if (step1Contents && step1Contents.navTitle) {
    return step1Contents.navTitle;
  }
  return toTitleCase(name) + " Case Study";
}

function updateBreadcrumb(step) {
  const el = document.getElementById("breadcrumbs");
  const caseStudyName = getCaseStudyDisplayName();

  // Reset breadcrumb
  el.innerHTML = "";

  // Helper to create items
  function addCrumb(label, onclick, isActive = false) {
    label = label.replace(/([a-z])([A-Z])/g, "$1 $2"); // "ExposureScenario" -> "Exposure Scenario"
    const li = document.createElement("li");
    li.classList.add("breadcrumb-item");

    if (isActive) {
      li.classList.add("active");
      li.classList.add("text-vhppink-distinct")
      li.setAttribute("aria-current", "page");
      li.textContent = label;
    } else {
      const a = document.createElement("a");
      a.href = "#";
      a.textContent = label;
      a.onclick = function (e) {
        e.preventDefault();
        onclick();
      };
      li.appendChild(a);
    }

    el.appendChild(li);
  }

  // Build breadcrumb depending on step
  addCrumb("Case Studies", () => (window.location.href = "/casestudies"));
  if (step === 1) {
    addCrumb(caseStudyName, null, true);
  } else if (step === 2) {
    addCrumb(caseStudyName, () => goToStep(1));
    addCrumb(`Regulatory Question ${currentStep1Value}`, null, true);
  } else if (step === 3) {
    addCrumb(caseStudyName, () => goToStep(1));
    addCrumb(`Regulatory Question ${currentStep1Value}`, () => goToStep(2));
    addCrumb(currentStep2Value, null, true);
  } else if (step === 4) {
    addCrumb(caseStudyName, () => goToStep(1));
    addCrumb(`Regulatory Question ${currentStep1Value}`, () => goToStep(2));
    addCrumb(currentStep2Value, () => goToStep(3));
    addCrumb(currentStep3Value, null, true);
  } else if (step === 5) {
    addCrumb(caseStudyName, () => goToStep(1));
    addCrumb(`Regulatory Question ${currentStep1Value}`, () => goToStep(2));
    addCrumb(currentStep2Value, () => goToStep(3));
    addCrumb(currentStep3Value, () => goToStep(4));
    addCrumb(currentStep4Value, null, true);
  } else if (step === 6) {
    addCrumb(caseStudyName, () => goToStep(1));
    addCrumb(`Regulatory Question ${currentStep1Value}`, () => goToStep(2));
    addCrumb(currentStep2Value, () => goToStep(3));
    addCrumb(currentStep3Value, () => goToStep(4));
    addCrumb(currentStep4Value, () => goToStep(5));
    addCrumb(currentStep5Value, null, true);
  }

  // Show/hide breadcrumb container
  const nav = el.closest("nav");
  if (step >= 2) {
    nav.classList.add("visible");
  } else {
    nav.classList.remove("visible");
  }


//---Updating URL from breadcrumb
const caseStudy = getCaseStudyNameFromUrl();
const base = "/casestudies/" + caseStudy;

const urlParts = [];

if (step >= 2 && currentStep1Value)
  urlParts.push(currentStep1Value);

if (step >= 3 && currentStep2Value)
  urlParts.push(currentStep2Value);

if (step >= 4 && currentStep3Value)
  urlParts.push(currentStep3Value);

if (step >= 5 && currentStep4Value)
  urlParts.push(currentStep4Value);

if (step >= 6 && currentStep5Value)
  urlParts.push(currentStep5Value);

const newUrl = base + (urlParts.length ? "/" + urlParts.join("/") : "");

const cleanedUrl = newUrl.replace(/%20/g, "_").replace(/\s+/g, "_");
history.pushState(null, "", cleanedUrl);

}

// Build Accordion HTML from JSON
function buildAccordionHTML(content) {
  if (!content || !Array.isArray(content)) return "";

  let html = `<div class="accordion" id="accordionMain">`;

  content.forEach((item, idx) => {
    const itemId = `accordionItem${idx}`;
    const isFirst = idx === 0;
    html += `
      <div class="accordion-item">
        <h2 class="accordion-header" id="heading${idx}">
          <button
            class="accordion-button ${!isFirst ? "collapsed" : ""}"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#${itemId}"
            aria-expanded="${isFirst}"
            aria-controls="${itemId}">
            ${item.section || `Section ${idx + 1}`}
          </button>
        </h2>
        <div
          id="${itemId}"
          class="accordion-collapse collapse ${isFirst ? "show" : ""}"
          aria-labelledby="heading${idx}"
          data-bs-parent="#accordionMain">
          <div class="accordion-body">
            ${item.description || ""}
          </div>
        </div>
      </div>`;
  });

  html += `</div>`;
  return html;
}

// Horizontal scroll navigation (snap to step)
function goToStep(step) {
  const wrapper = document.getElementById("stepsWrapper");
  const width = window.innerWidth;
  const scrollAmount = width * (step - 1);
  const duration = 1000; // ms
  const start = wrapper.scrollLeft;
  const change = scrollAmount - start;
  const startTime = performance.now();
  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }
  function animateScroll(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const ease = easeInOutCubic(progress);
    wrapper.scrollLeft = start + change * ease;
    if (progress < 1) {
      requestAnimationFrame(animateScroll);
    }
  }
  requestAnimationFrame(animateScroll);
  updateBreadcrumb(step);
  updateWorkflowHeader(step);
  if (step === 1) updateStep1Content();
  if (step === 2) updateStep2Content();
  if (step === 3) updateStep3Content();
  if (step === 4) updateStep4Content();
  if (step === 5) updateStep5Content();
  if (step === 6) updateStep6Content();
}

// Function to make the workflowheader interactive
function updateWorkflowHeader(activeStepNumber) {
  const steps = document.querySelectorAll(".step-item");

  steps.forEach(step => {
    step.classList.remove("active", "completed");
    const stepNum = parseInt(step.getAttribute("data-step"));

    if (stepNum < activeStepNumber) {
      step.classList.add("completed");
    } else if (stepNum === activeStepNumber) {
      step.classList.add("active");
    }
  });
}

// Function for backward clickability of the step-icons in the workflow header
let currentStep=1;
function initWorkflowHeaderClicks() {
  const steps = document.querySelectorAll(".step-item");

  steps.forEach(step => {
    step.addEventListener("click", () => {
      const stepNum = parseInt(step.getAttribute("data-step"));
      if (stepNum <= currentStep) { //Goes back to step 1 (start of the workflow)
         goToStep(stepNum); 
      }
    });
  });
}


// --- Load content from JSON and initialize ---
document.addEventListener("DOMContentLoaded", function () {
  loadCaseStudyContent();
});


// Creating URL from breadcrumb
window.addEventListener("popstate", () => {
applyStateFromUrl();
});
function applyStateFromUrl() {
const parts = window.location.pathname.split("/").filter(Boolean);
const crumbs = parts;
console.log(crumbs)
console.log(crumbs.length)

// Links from elsewhere (e.g. the data page) arrive percent-encoded and may use
// the question label ("Question 2: ...") instead of its key ("Q2").
const seg = (i) => {
  const s = (crumbs[i] || "").replace(/_/g, " ");
  try { return decodeURIComponent(s); } catch (e) { return s; }
};
currentStep1Value = seg(2);
currentStep2Value = seg(3);
currentStep3Value = seg(4);
currentStep4Value = seg(5);
currentStep5Value = seg(6);
if (contentLoaded) resolveUrlState();

const step = getCurrentStepNumber();
goToStep(step);
return step;
}

// Snap URL values onto the config keys: questions match by key or label,
// steps case-insensitively. The first value that doesn't resolve (and all
// after it) is dropped, so the page stops at the deepest valid step instead
// of rendering blank.
function resolveUrlState() {
  const same = (a, b) => (a || "").toLowerCase() === (b || "").toLowerCase();
  const q = (step1Contents.questions || []).find(
    (q) => same(q.value, currentStep1Value) || same(q.label, currentStep1Value)
  );
  const vals = [q ? q.value : "", currentStep2Value, currentStep3Value, currentStep4Value, currentStep5Value];
  [step3Contents, step4Contents, step5Contents, step6Contents].forEach((level, i) => {
    let node = level;
    for (let j = 0; j <= i && node; j++) node = node[vals[j]];
    vals[i + 1] = (node && Object.keys(node).find((k) => same(k, vals[i + 1]))) || "";
  });
  [currentStep1Value, currentStep2Value, currentStep3Value, currentStep4Value, currentStep5Value] = vals;
}


function getCurrentStepNumber() {
  if (currentStep5Value != "") return 6;
  if (currentStep4Value != "") return 5;
  if (currentStep3Value != "") return 4;
  if (currentStep2Value != "") return 3;
  if (currentStep1Value != "") return 2;
  return 1;
}
