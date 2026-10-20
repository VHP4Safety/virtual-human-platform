/**
 * Fetches ontology label information from EBI OLS4 API for a given IRI.
 * Updates the provided anchor element with the label and short form.
 * 
 * @param {HTMLAnchorElement} anchorElement - The anchor element to update
 * @param {string} iri - The ontology IRI (e.g., "http://purl.obolibrary.org/obo/GO_0008150")
 * @returns {Promise<void>}
 */
async function getOntologyLabel(anchorElement, iri) {
    if (!anchorElement || !iri || !iri.startsWith('http')) {
        return;
    }

    const encodedIri = encodeURIComponent(encodeURIComponent(iri));
    const apiUrl = `https://www.ebi.ac.uk/ols4/api/terms/${encodedIri}?lang=en`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            return;
        }

        const data = await response.json();
        const term = data._embedded?.terms?.[0];

        if (term) {
            // Update anchor text with label and optional short form
            const shortForm = term.short_form || term.ontology_prefix;
            anchorElement.textContent = shortForm 
                ? `${term.label} (${shortForm})` 
                : term.label;
            
            // Construct OLS page URL
            // Format: https://www.ebi.ac.uk/ols4/ontologies/{ontology_name}/classes/{double-encoded IRI}
            if (term.ontology_name) {
                anchorElement.href = `https://www.ebi.ac.uk/ols4/ontologies/${term.ontology_name}/classes/${encodedIri}`;
            }
        }
    } catch (error) {
        // Silently fail - keep original IRI as text
        console.warn('Failed to fetch ontology label for:', iri, error);
    }
}

/**
 * Processes all ontology IRI links on the page.
 * Looks for anchor elements with hrefs starting with common ontology prefixes.
 * 
 * @param {string} selector - Optional CSS selector to limit scope (default: defaultSelector)
 * @param {number} delay - Delay between API calls in ms (default: 100)
 * @returns {Promise<void>}
 */
async function processOntologyLinks(selector, delay = 100) {
    // Ontology-specific prefixes
    const defaultSelector = [
        'a[href^="http://purl.obolibrary.org"]',      // OBO Foundry ontologies
        'a[href^="http://purl.enanomapper.org"]',     // eNanoMapper ontology
        'a[href^="http://purl.bioontology.org"]',     // BioPortal ontologies
        'a[href^="http://id.nlm.nih.gov/mesh"]',      // MeSH terms
        'a[href^="https://purl.obolibrary.org"]',     // OBO Foundry (https)
        'a[href^="http://www.ebi.ac.uk/efo"]',        // EFO ontology
        'a[href^="http://semanticscience.org"]',      // SIO ontology
        'a[href^="http://www.orpha.net"]'             // Orphanet
    ].join(', ');
    const links = document.querySelectorAll(selector || defaultSelector);

    for (const link of links) {
        await getOntologyLabel(link, link.href);
        // Rate limiting to avoid overwhelming the API
        await new Promise(resolve => setTimeout(resolve, delay));
    }
}
