/* ============================================================================
   Dynamic search results- Fuse.js
   ============================================================================ */

//This script uses fuse.js to generate a dynamic searchbar that shows live-dropdown suggestions with inclusion of typo tolerance and matches. Important settings of Fuse.js include: 
// keys: ["title"]: searches page titles
// threshold: 0.4: At what point does the match algorithm give up.
// minMatchCharLength: at least 2 characters needed to search
// IncludeScore: will include the score for each match in the search results
// IncludeMatches: will include the matches and their positions within the search results
// ignoreLocation:  match anywhere in the title
//Explanation:
// The script starts off by creating an array with the platform's pages as the entrypoint for Fuse.js. Next fuse.js is initialised and the javascript is connected to the HTML to integrate the searchinput, resultscontainer and search button so that when users type input into the searchbar, results are shown dynamically underneath it (dropdown) and for no results, a message appears. The matched typed text will be shown as highlighted pink and each result is clickable. So when users click on the result in the dropdown, it will take them to the page URL. In addition, every time the user clicks outside the search area, the dropdown disappears which keeps the UI organized (additional step).


//Step 1:Pages array with titles and URLs as entrypoint for fuse.js
function normalize(raw, url_prefix) {
  if (!raw) return [];
  // If already an array of {id, title}, return normalized
  if (Array.isArray(raw)) {
    return raw.map(it => ({ title: it.title || it.service || it.label || it.id || '', url: it.url || it.mainUrl || it.mainUrl || url_prefix + it.id }));
  }
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw);
      return normalize(parsed);
    } catch (err) {
      return [];
    }
  }
  if (typeof raw === 'object') {
    return Object.keys(raw).map(k => ({ title: raw[k].service || raw[k].title || raw[k].label || k, url: raw[k].url || url_prefix + it.id }));
  }
  return [];
}


async function waitForGlobal(name, { timeout = 5000, interval = 50 } = {}) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    if (window[name] !== undefined) return window[name];
    await new Promise(r => setTimeout(r, interval));
  }
  throw new Error(`Timed out waiting for window.${name}`);
}

let pages = [];
// Initalize Search after we have tools and methods available
(async () => {
  try {
    const toolsMenu = await waitForGlobal("TOOLS_MENU", { timeout: 8000 });
    const methodsMenu = await waitForGlobal("METHODS_MENU", {timeout:8000});
    const dataMenu = await waitForGlobal("DATA_MENU", {timeout:8000});

    tools = normalize(toolsMenu, "/tools/");
    methods = normalize(methodsMenu, "/methods/")
    data = normalize(dataMenu, "")

    // collate search pages
    const homeEntry = [  
       //{ title: "Home", url: "/" }
    ]

    const toolsHome = [
      //{ title: "Tools Overview", url: "/tools" },
    ]
    const methodsHome = [
      //{title: "Methods Overview", url: "/methods"}
    ]

    const caseStudies = [
      // Case Studies
      //{ title: "Case Studies", url: "/casestudies" },
      { title: "Thyroid Case Study", url: "/casestudies/thyroid" },
      { title: "Parkinson Case Study", url: "/casestudies/parkinson" },
      { title: "Kidney Case Study", url: "/casestudies/kidney" },
    ]

      // Data & Home
    const dataEntry=[
      //{ title: "Data Overview", url: "/data" },
    ];

    pages = [...homeEntry,...caseStudies,...toolsHome,...tools,...methodsHome,...methods,...dataEntry,...data]

    

    //Step 2: Initialization of Fuse.js and connection between Fuse and HTML
    const fuse = new Fuse(pages, {
      keys: ["title"],
      threshold: 0.4,       // Setting for typo tolerance
      distance: 100,  //determines how close the match is to the fuzzy location. Default is 100
      minMatchCharLength: 2, //Minimum length of characters needed to search
      IncludeMatches: true, 
      ignoreLocation: true //To match anywhere in the title
    });

    const pairs = [
      { input: document.getElementById("searchInput"),        container: document.getElementById("results") },
      { input: document.getElementById("searchInputMobile"),  container: document.getElementById("resultsMobile") },
    ].filter(p => p.input && p.container); // optional: avoid nulls if one doesn't exist on a page

    function renderResults(container, results, query) {
      if (!results.length) {
        container.innerHTML = `<li class="list-group-item">No results found for "${escapeHtml(query)}"</li>`;
        return;
      }

      // Escape query for regex, otherwise special chars break highlighting
      const safeQuery = escapeRegExp(query);
      const regex = new RegExp(`(${safeQuery})`, "gi");

      container.innerHTML = results
        .map(r => {
          const title = r.item.title ?? "";
          const url = r.item.url ?? "#";

          const highlightedTitle = escapeHtml(title).replace(regex, `<mark>$1</mark>`);

          return `<a class="list-group-item" href="${escapeAttr(url)}" style="text-decoration:none; color:inherit;">
                      ${highlightedTitle}
                    </a>`;
        })
        .join("");
    }

    // Bind each input to its own container
    pairs.forEach(({ input, container }) => {
      input.addEventListener("input", () => {
        const query = input.value.trim();

        if (!query) {
          container.innerHTML = "";
          return;
        }

        const results = fuse.search(query); // assumes fuse is defined
        renderResults(container, results, query);
      });
    });



  } catch (err) {
    console.warn(err.message);
  }
})();



// ---------- helpers ----------
function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Minimal escaping to avoid HTML injection in titles / query
function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(str) {
  // For href etc. Very simple safe-escape.
  return escapeHtml(str);
}



//Step 4: enable live search (dynamically seeing results when user is typing)


//Step 5: redirect to first match when clicking search button
// searchBtn.addEventListener("click", () => {
//   const query = searchInput.value.trim();
//   if (!query) return;

//   const results = fuse.search(query);
//   if (results.length > 0) {
//     window.location.href = results[0].item.url;
//   } else {
//     alert(`No results found for "${query}"`);
//   }
// });


