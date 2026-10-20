/**
 * Ontology Widget - Wrapper for ts4nfdi Terminology Service Suite
 * Displays metadata for ontology terms using their IRI
 */

// Common ontology namespace to prefix mappings
const ONTOLOGY_PREFIXES = {
  // Anatomy & Physiology
  'UBERON': 'uberon',
  'FMA': 'fma',
  'CL': 'cl',
  'GO': 'go',
  'MESH': 'mesh',
  // Chemistry
  'CHEBI': 'chebi',
  'CHEMINF': 'cheminf',
  'CHMO': 'chmo',
  'BAO': 'bao',
  'ENM': 'enm',
  
  // Disease & Phenotype
  'DOID': 'doid',
  'HP': 'hp',
  'MP': 'mp',
  'MONDO': 'mondo',
  
  // Environment & Exposure
  'ENVO': 'envo',
  'ECTO': 'ecto',
  'ExO': 'exo',
  
  // Adverse Outcome Pathways
  'AOP': 'aop',
  'AOPO': 'aopo',
  
  // Taxonomy
  'NCBITaxon': 'ncbitaxon',
  'TAXRANK': 'taxrank',
  
  // Units & Measurements
  'UO': 'uo',
  'PATO': 'pato',
  
  // Experimental
  'OBI': 'obi',
  'BAO': 'bao',
  'EFO': 'efo',
  
  // Information & Data
  'IAO': 'iao',
  'SIO': 'sio',
  'EDAM': 'edam',
  
  // Biological Processes
  'PR': 'pr',
  'SO': 'so',
  'PO': 'po',
  
  // Toxicology
  'TOXRIC': 'toxric',
  'CDNO': 'cdno',
  
  // General
  'BFO': 'bfo',
  'RO': 'ro',
  'OWL': 'owl',
  'NCIT': 'ncit'
};

/**
 * Extract ontology ID from an IRI
 * Supports formats like:
 *   http://purl.obolibrary.org/obo/UBERON_0001443
 *   http://purl.obolibrary.org/obo/CHEBI_12345
 *   http://www.ebi.ac.uk/efo/EFO_0000001
 */
function getOntologyIdFromIri(iri) {
  if (!iri) return '';
  
  // Try OBO format: /obo/PREFIX_id
  let match = iri.match(/\/obo\/([A-Za-z]+)_/);
  if (match) {
    const prefix = match[1].toUpperCase();
    return ONTOLOGY_PREFIXES[prefix] || prefix.toLowerCase();
  }
  
  // Try EFO format: /efo/EFO_id
  match = iri.match(/\/efo\/([A-Za-z]+)_/);
  if (match) {
    const prefix = match[1].toUpperCase();
    return ONTOLOGY_PREFIXES[prefix] || prefix.toLowerCase();
  }
  
  // Try generic format with hash: #ClassName
  match = iri.match(/\/([a-zA-Z]+)#/);
  if (match) {
    const prefix = match[1].toUpperCase();
    return ONTOLOGY_PREFIXES[prefix] || prefix.toLowerCase();
  }
  
  // Fallback: try to find any known prefix in the IRI
  for (const [prefix, id] of Object.entries(ONTOLOGY_PREFIXES)) {
    if (iri.toUpperCase().includes(prefix)) {
      return id;
    }
  }
  
  return '';
}

function initOntologyWidget(iri, containerId) {
  if (!iri || !containerId) {
    console.warn('[ontology_widget] Missing iri or containerId');
    return;
  }

  const container = document.querySelector(containerId);
  if (!container) {
    console.warn('[ontology_widget] Container not found:', containerId);
    return;
  }

  const ontologyId = getOntologyIdFromIri(iri);
  console.log('[ontology_widget] IRI:', iri, '-> ontologyId:', ontologyId);

  // Check if ts4nfdiWidgets is loaded
  if (typeof window['ts4nfdiWidgets'] === 'undefined') {
    container.innerHTML = '<p class="text-muted">Loading ontology widget...</p>';
    setTimeout(() => initOntologyWidget(iri, containerId), 500);
    return;
  }

  window['ts4nfdiWidgets'].createMetadata(
    {
      iri: iri,
      ontologyId: ontologyId,
      api: "https://www.ebi.ac.uk/ols4/api/", // Using OLS API, so far most complete
      entityType: "term",
      parameter: "",
      useLegacy: true,
      termLink: "",
      altNamesTab: true,
      hierarchyTab: true,
      crossRefTab: true,
      terminologyInfoTab: true,
      graphViewTab: true,
      termDepictionTab: true,
      hierarchyPreferredRoots: false,
      hierarchyKeepExpansionStates: false,
      hierarchyShowSiblingsOnInit: false,
      onNavigateToEntity: (e, t, r) => {
        if (r && r.iri) window.open(r.iri, '_blank');
      },
      onNavigateToOntology: (e, t, r) => {
        console.log('Navigate to ontology:', e);
      },
      onNavigateToDisambiguate: (e, t) => {
        console.log('Disambiguate:', e);
      },
      className: ""
    },
    container
  );
}
