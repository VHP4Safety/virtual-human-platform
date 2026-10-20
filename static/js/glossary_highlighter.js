/**
 * VHP4Safety Glossary Term Highlighter
 */

(function () {
  'use strict';

  const GLOSSARY_OWL_URL  = 'https://raw.githubusercontent.com/VHP4Safety/glossary/refs/heads/main/glossary.owl';
  const GLOSSARY_SITE_URL = 'https://glossary.vhp4safety.nl/';
  const SKIP_TAGS = new Set([
    'script', 'style', 'noscript', 'iframe', 'object',
    'button', 'select', 'option', 'textarea', 'input',
    'a', 'label', 'code', 'pre', 'kbd', 'samp', 'var',
    'nav', 'footer', 'header',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'svg', 'canvas', 'img', 'video', 'audio',
  ]);

  const SKIP_CLASSES = [
    'btn', 'nav-link', 'navbar', 'dropdown-item', 'dropdown-toggle', 'dropdown-menu',
    'accordion-button', 'accordion-header',
    'offcanvas', 'modal', 'toast', 'popover', 'tooltip',
    'breadcrumb', 'pagination',
    'form-control', 'form-select', 'form-check', 'input-group',
    'badge', 'alert', 'spinner',
    'card-button', 'card-header', 'card-footer', 'card-title',
    'visually-hidden',
    'search-results',
    'vhp-highlight', 'highlighted',
  ];

  // Helpers

  const escapeHtml  = t => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
  const escapeRegex = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  function glossaryUrl(uri) {
    return uri?.includes('#') ? `${GLOSSARY_SITE_URL}#${uri.split('#')[1]}` : GLOSSARY_SITE_URL;
  }

  // Parsing glossary

  function parseGlossary(turtleText) {
    const rx = /<([^>]+)>\s*\n([\s\S]*?)(?=\n<|$)/g;
    const prop = (block, p) => { const m = block.match(p); return m ? m[1].trim() : ''; };
    const terms = [];
    let m;

    while ((m = rx.exec(turtleText)) !== null) {
      const [, uri, block] = m;
      if (!block.includes('rdf:type') || !block.includes('owl:Class')) continue;

      const label = prop(block, /rdfs:label\s+"([^"]+)"(?:@[a-zA-Z-]+)?/);
      if (!label || label === 'nan' || label.length < 2) continue;

      const term = { uri, label,
        definition: prop(block, /dc:description\s+"([^"]+)"(?:@[a-zA-Z-]+)?/),
        synonyms:   [],
      };
      const syn = prop(block, /ncit:C42610\s+"([^"]+)"(?:@[a-zA-Z-]+)?/);
      if (syn) term.synonyms.push(syn);
      const smiles = prop(block, /chebi:smiles\s+"([^"]+)"(?:@[a-zA-Z-]+)?/);
      if (smiles) term.smiles = smiles;
      terms.push(term);
    }
    return terms;
  }

  // Node filtering

  function isProcessable(node) {
    if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) return false;

    for (let el = node.parentElement; el; el = el.parentElement) {
      if (SKIP_TAGS.has(el.tagName.toLowerCase())) return false;
      if (el.hasAttribute('data-vhp-glossary') || el.hasAttribute('data-vhp-glossary-skip')) return false;
      if (el.hasAttribute('data-bs-toggle') || el.hasAttribute('data-bs-dismiss')) return false;
      if (el.isContentEditable) return false;
      const classes = el.classList;
      if (SKIP_CLASSES.some(c => classes.contains(c))) return false;
    }
    return true;
  }

  function collectTextNodes(root) {
    const nodes = [];
    (function walk(n) {
      if (n.nodeType === Node.TEXT_NODE) { if (isProcessable(n)) nodes.push(n); }
      else if (n.nodeType === Node.ELEMENT_NODE) n.childNodes.forEach(walk);
    })(root);
    return nodes;
  }

  // Matching and highlighting

  function findMatches(text, terms) {
    const matches = [];
    for (const term of terms) {
      for (const label of [term.label, ...term.synonyms]) {
        const regex = new RegExp(`\\b${escapeRegex(label)}\\b`, 'gi');
        let m;
        while ((m = regex.exec(text)) !== null) {
          matches.push({ start: m.index, end: m.index + m[0].length, text: m[0], term });
        }
      }
    }
    // Of overlapping matches, the longest match that starts first is kept, such as "AOP-Wiki RDF" over "RDF".
    matches.sort((a, b) => a.start - b.start || b.end - a.end);
    const kept = [];
    for (const m of matches) {
      if (!kept.length || m.start >= kept[kept.length - 1].end) kept.push(m);
    }
    return kept;
  }

  function tooltipHtml(term) {
    let html = `<strong>${escapeHtml(term.label)}</strong>`;
    if (term.definition) html += `<br><small>${escapeHtml(term.definition)}</small>`;
    if (term.synonyms.length) html += `<br><small>Synonyms: ${escapeHtml(term.synonyms.join(', '))}</small>`;
    html += `<div class="mt-1"><a href="${escapeHtml(glossaryUrl(term.uri))}" target="_blank" rel="noopener noreferrer" class="link-light text-decoration-underline"><i class="bi bi-box-arrow-up-right"></i> View full definition</a></div>`;
    return html;
  }

  function createSpan(match) {
    const span = document.createElement('span');
    span.textContent = match.text;
    span.setAttribute('data-vhp-glossary', '');
    span.setAttribute('role', 'term');
    span.classList.add('d-inline', 'p-0', 'rounded');

    span.setAttribute('data-bs-toggle', 'tooltip');
    span.setAttribute('data-bs-html', 'true');
    span.setAttribute('data-bs-placement', 'bottom');
    span.setAttribute('title', tooltipHtml(match.term));
    span.setAttribute('data-vhp-uri', match.term.uri);
    return span;
  }

  function highlightNode(node, terms) {
    const text = node.textContent;
    const matches = findMatches(text, terms);
    if (!matches.length) return;

    const frag = document.createDocumentFragment();
    let last = 0;
    for (const m of matches) {
      if (m.start > last) frag.appendChild(document.createTextNode(text.substring(last, m.start)));
      frag.appendChild(createSpan(m));
      last = m.end;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.substring(last)));
    node.parentNode.replaceChild(frag, node);
  }

  // Tooltips

  function initTooltips() {
    if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) return;

    let activeTooltip = null;

    document.querySelectorAll('[data-vhp-glossary][data-bs-toggle="tooltip"]').forEach(el => {
      const title = el.getAttribute('title');
      if (!title || !title.trim() || title === 'null' || title === 'undefined') return;

      const tip = new bootstrap.Tooltip(el, {
        html:        true,
        trigger:     'click',
        container:   'body',
        placement:   'bottom',
        customClass: 'vhp-glossary-tooltip-fixed',
      });

      el.addEventListener('show.bs.tooltip', () => {
        if (activeTooltip && activeTooltip !== tip) activeTooltip.hide();
        activeTooltip = tip;
      });

      el.addEventListener('hidden.bs.tooltip', () => {
        if (activeTooltip === tip) activeTooltip = null;
      });
    });

    document.addEventListener('click', e => {
      if (!activeTooltip) return;
      const span = activeTooltip._element;
      const popup = activeTooltip.tip;
      if (span?.contains(e.target) || popup?.contains(e.target)) return;
      activeTooltip.hide();
    });
  }

  //  Boot

  let glossaryActive = false;

  function setGlossaryVisible(visible) {
    glossaryActive = visible;
    document.querySelectorAll('[data-vhp-glossary]').forEach(span => {
      span.classList.toggle('bg-vhplight-blue', visible);
      span.classList.toggle('bg-opacity-50', visible);
      if (visible) {
        span.setAttribute('data-bs-toggle', 'tooltip');
      } else {
        const tip = bootstrap.Tooltip.getInstance(span);
        if (tip) tip.dispose();
        span.removeAttribute('data-bs-toggle');
      }
    });
    const toggle = document.getElementById('glossary-toggle');
    if (toggle) toggle.checked = visible;
    const toggleMobile = document.getElementById('glossary-toggle-mobile');
    if (toggleMobile) toggleMobile.checked = visible;
    if (visible) initTooltips();
  }

  // The hint is shown until the switch is used once.
  function showHint(toggle) {
    if (localStorage.getItem('vhp-glossary-active') !== null) return;
    const wrapper = toggle.closest('.form-check') || toggle;
    const hint = new bootstrap.Popover(wrapper, {
      content:   'Toggle to highlight glossary terms on the page',
      placement: 'bottom',
      trigger:   'manual',
      offset:    [0, 10],
      container: wrapper.closest('.navbar') || 'body',
    });
    hint.show();
    const dismiss = () => { hint.dispose(); toggle.removeEventListener('change', dismiss); };
    toggle.addEventListener('change', dismiss);
    setTimeout(dismiss, 4000);
  }

  async function run() {
    try {
      const resp = await fetch(GLOSSARY_OWL_URL);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const terms = parseGlossary(await resp.text());
      if (!terms.length) { return; }

      const nodes = collectTextNodes(document.body);
      for (const node of nodes) {
        try { highlightNode(node, terms); }
        catch (e) { return }
      }

      const savedState = localStorage.getItem('vhp-glossary-active') === '1';
      setGlossaryVisible(savedState);

      const toggle = document.getElementById('glossary-toggle');
      if (toggle) {
        toggle.addEventListener('change', () => {
          localStorage.setItem('vhp-glossary-active', toggle.checked ? '1' : '0');
          setGlossaryVisible(toggle.checked);
        });
        showHint(toggle);
      }
    } catch (e) {
      return;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(run, 500));
  } else {
    run();
  }
})();
