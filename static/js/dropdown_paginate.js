(() => {
  /**
   * Initialize a paginated dropdown.
   * menuId: id of the <ul class="dropdown-menu"> element
   * toggleBtnId: id of the button that toggles the dropdown
   * options: { pageSize, items, urlPrefix } - items can override window.TOOLS_MENU
   */
  function initPaginatedDropdown(menuId, toggleBtnId, options = {}) {
    const menu = document.getElementById(menuId);
    const toggleBtn = document.getElementById(toggleBtnId);
    if (!menu || !toggleBtn) {
      console.debug('initPaginatedDropdown: missing elements', menuId, toggleBtnId);
      return null;
    }

    const PAGE_SIZE = parseInt(menu.dataset.pageSize || options.pageSize || 12, 10) || 12;
    const URL_PREFIX = options.urlPrefix || "";

    function buildMainUrl(primaryUrl, secondaryUrl, id) {
      if (primaryUrl) return primaryUrl;
      if (secondaryUrl) return secondaryUrl;
      if (id) return URL_PREFIX + id;
      return '';
    }

    function normalize(raw) {
      if (!raw) return [];
      // If already an array of {id, title}, return normalized
      if (Array.isArray(raw)) {
        return raw.map(it => {
          const id = it.id || it.key || it.name || '';
          return {
            id,
            title: it.title || it.service || it.label || it.id || '',
            main_url: buildMainUrl(it.main_url, it.mainUrl, id)
          };
        });
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
        return Object.keys(raw).map(k => ({
          id: k,
          title: raw[k].service || raw[k].title || raw[k].label || k,
          main_url: buildMainUrl(raw[k].main_url, raw[k].mainUrl, k)
        }));
      }
      return [];
    }

    // Determine items: options.items > named global > data-tools attribute
    // Only fall back to window.TOOLS_MENU automatically for the default toolsMenu
    let items = [];
    if (typeof options.items === 'string') {
      // resolve by global name e.g. 'METHODS_MENU' or 'tools_menu'
      items = window[options.items] || window[options.items.toUpperCase()] || window[options.items.toLowerCase()] || [];
    } else if (Array.isArray(options.items) && options.items.length) {
      items = options.items;
    } else if (menu.dataset.tools) {
      items = menu.dataset.tools;
    } else if (menuId === 'toolsMenu' && window.TOOLS_MENU) {
      // legacy global fallback only for the toolsMenu
      items = window.TOOLS_MENU;
    }

    items = normalize(items);

    // If items empty, try a few short retries in case of ordering differences
    let attempts = 0;
    function ensureItemsReady(cb) {
      attempts += 1;
      if (items.length === 0 && attempts <= 3) {
        if (window.TOOLS_MENU && window.TOOLS_MENU.length) items = normalize(window.TOOLS_MENU);
        else if (menu.dataset.tools) items = normalize(menu.dataset.tools);
        if (items.length === 0) setTimeout(() => ensureItemsReady(cb), 50);
        else cb();
      } else cb();
    }

    let page = 0;
    // Determine CSS classes for the 'More' / 'Back to top' action item.
    // options.moreClasses can be a string of classes (e.g. 'text-vhpblue') or omitted.
    const moreClasses = (options.moreClasses || menu.dataset.moreClasses || 'text-primary').toString();
    // Per-element classes for the inner spans (text and arrow) so each menu can style them.
    // options.moreTextClass or data-more-text-class controls the "More" / "Back to top" text span.
    // options.moreArrowClass or data-more-arrow-class controls the arrow span.
    const moreTextClass = (options.moreTextClass || menu.dataset.moreTextClass || moreClasses).toString();
    const moreArrowClass = (options.moreArrowClass || menu.dataset.moreArrowClass || moreClasses).toString();

    function render() {
      menu.innerHTML = '';
      if (!items || items.length === 0) {
        const li = document.createElement('li');
        const div = document.createElement('div');
        div.className = 'dropdown-item text-muted';
        div.textContent = 'No tools available';
        li.appendChild(div);
        menu.appendChild(li);
        return;
      }

      const start = page * PAGE_SIZE;
      const slice = items.slice(start, start + PAGE_SIZE);
      if (slice.length === 0) {
        page = 0;
        return render();
      }

      slice.forEach(item => {
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.className = 'dropdown-item';
        a.href = item.main_url || '#';
        a.textContent = item.title || item.id || '';
        a.dataset.id = item.id || '';
        li.appendChild(a);
        menu.appendChild(li);
      });

      const hasMore = start + PAGE_SIZE < items.length;
      const moreLi = document.createElement('li');
      const moreA = document.createElement('a');
      moreA.className = 'dropdown-item more ' + moreClasses;
      moreA.href = '#';

      // Build inner spans so callers can style them independently
      const textSpan = document.createElement('span');
      textSpan.className = moreTextClass;
      const arrowSpan = document.createElement('span');
      arrowSpan.className = moreArrowClass;
      arrowSpan.setAttribute('aria-hidden', 'true');

      if (hasMore) {
        moreA.dataset.action = 'more';
        textSpan.textContent = 'More';
        arrowSpan.textContent = '▾';
      } else {
        moreA.dataset.action = 'top';
        textSpan.textContent = 'Back to top';
        arrowSpan.textContent = '▴';
      }

      moreA.appendChild(textSpan);
      moreA.appendChild(document.createTextNode(' '));
      moreA.appendChild(arrowSpan);
      moreLi.appendChild(moreA);
      menu.appendChild(moreLi);
    }

    menu.addEventListener('click', (e) => {
      const a = e.target.closest('a');
      if (!a) return;
      const action = a.dataset.action;
      if (action === 'more') {
        e.preventDefault();
        e.stopPropagation();
        page += 1;
        render();
        menu.querySelector('.dropdown-item:not(.more)')?.focus();
        return;
      }
      if (action === 'top') {
        e.preventDefault();
        e.stopPropagation();
        page = 0;
        render();
        menu.querySelector('.dropdown-item:not(.more)')?.focus();
        return;
      }
      // other links: let bootstrap close dropdown naturally
    });

    toggleBtn.addEventListener('show.bs.dropdown', () => { page = 0; render(); });

    // Start after ensuring items available
    ensureItemsReady(render);

    return { render, getItems: () => items };
  }

  // Initialize the default tools dropdown
  window.initPaginatedDropdown = initPaginatedDropdown;
  // store instances so we don't double-initialize
  window._paginatedDropdowns = window._paginatedDropdowns || {};

  // Helper: auto-init a paginated dropdown in a symmetric way for any menu.
  function autoInitMenu(menuId, btnId, optionsOrDefault) {
    try {
      const menuEl = document.getElementById(menuId);
      const btnEl = document.getElementById(btnId);
      if (!menuEl || !btnEl) return null;

      // Normalize options: allow passing a string as the default global name or an options object
      const opts = (typeof optionsOrDefault === 'string') ? { defaultGlobalName: optionsOrDefault } : (optionsOrDefault || {});

      // Determine a preferred global name from data-source attribute or provided default
      const ds = menuEl.dataset.source || opts.defaultGlobalName || null;

      const tryInit = (sourceOverride) => {
        try {
          // Resolve items: explicit override, named global, or dataset.tools
          let items = null;
          if (sourceOverride) items = sourceOverride;
          else if (opts.items) {
            // opts.items may be a string naming a global, or an array
            if (typeof opts.items === 'string') items = window[opts.items] || window[opts.items.toUpperCase()] || window[opts.items.toLowerCase()] || null;
            else items = opts.items;
          } else if (ds && window[ds]) items = window[ds];
          else if (menuEl.dataset.tools) items = JSON.parse(menuEl.dataset.tools);

          if (items) {
            const inst = window.initPaginatedDropdown(menuId, btnId, { items, moreClasses: opts.moreClasses, moreTextClass: opts.moreTextClass, moreArrowClass: opts.moreArrowClass, pageSize: opts.pageSize, urlPrefix: opts.urlPrefix,  });
            return inst;
          }
        } catch (err) {
          console.debug('autoInitMenu tryInit error for', menuId, err);
        }
        return null;
      };

      // First try immediate init
      let inst = tryInit();
      if (inst) return window._paginatedDropdowns[menuId] = inst;

      // If not available yet, poll for a short period and also listen for first open
      let attempts = 0;
      const poll = setInterval(() => {
        attempts += 1;
        inst = tryInit();
        if (inst || attempts > 50) {
          clearInterval(poll);
        }
        if (inst) window._paginatedDropdowns[menuId] = inst;
      }, 100);

      const onShow = () => {
        const res = tryInit();
        if (res) {
          window._paginatedDropdowns[menuId] = res;
          btnEl.removeEventListener('show.bs.dropdown', onShow);
          clearInterval(poll);
        }
      };
      btnEl.addEventListener('show.bs.dropdown', onShow);

      return null;
    } catch (err) {
      console.debug('autoInitMenu failed for', menuId, err);
      return null;
    }
  }

  // Symmetrically initialize both menus (they share the same behavior)
  autoInitMenu('toolsMenu', 'toolsMenuBtn', {items: 'TOOLS_DROPDOWN',moreClasses:"text-vhpblue", urlPrefix:"/tools/"});
  autoInitMenu('methodsMenu', 'methodsMenuBtn', {items: 'METHODS_MENU', moreClasses:"text-vhpdarkpurple", urlPrefix:"/methods/"});
})();
