/**
 * Search and Filter Module
 * Provides reusable search and filter functionality for catalog pages (data, methods, tools)
 * 
 * Usage:
 * SearchFilter.init({
 *   filterTypes: ['case-study', 'flow-step', 'reg-question'], // Filter categories
 *   multiSelect: false, // Whether to allow multiple selections per category
 *   initialFilters: { 'case-study': 'Kidney', ... }, // Initial filter values from server
 *   formElementIds: { // Optional: Override default element IDs
 *     form: 'search-form',
 *     filterToggle: 'filter-toggle-btn',
 *     filterPanel: 'filter-panel',
 *     applyBtn: 'apply-filter-btn',
 *     clearBtn: 'clear-filter-btn',
 *     filterTags: 'filter-tags',
 *     selectedFilters: 'selected-filters'
 *   },
 *   filterFieldMap: { // Map filter types to hidden form field IDs
 *     'case-study': 'filter_case_study',
 *     'flow-step': 'filter_flow_step',
 *     'reg-question': 'filter_regulatory_question'
 *   },
 *   filterLabels: { // Human-readable labels for filter types
 *     'case-study': 'Case Study',
 *     'flow-step': 'Flow Step',
 *     'reg-question': 'Reg. Question'
 *   },
 *   badgeClass: 'badge rounded-pill text-bg-vhpteal', // CSS class for filter tags
 *   initTooltips: true, // Whether to initialize Bootstrap tooltips
 *   tooltipSelector: '[data-bs-toggle="tooltip"]' // Selector for tooltips
 * });
 */

(function(window) {
  'use strict';

  const SearchFilter = {
    config: null,
    elements: null,
    selectedFilters: {},

    /**
     * Initialize the search and filter functionality
     */
    init(options) {
      // Set default configuration
      this.config = {
        filterTypes: options.filterTypes || [],
        multiSelect: options.multiSelect !== undefined ? options.multiSelect : false,
        multipleInputs: options.multipleInputs || false, // Create separate input for each value
        initialFilters: options.initialFilters || {},
        formElementIds: {
          form: 'search-form',
          filterToggle: 'filter-toggle-btn',
          filterPanel: 'filter-panel',
          applyBtn: 'apply-filter-btn',
          clearBtn: 'clear-filter-btn',
          filterTags: 'filter-tags',
          selectedFilters: 'selected-filters',
          ...(options.formElementIds || {})
        },
        filterFieldMap: options.filterFieldMap || {},
        filterLabels: options.filterLabels || {},
        badgeClass: options.badgeClass || 'badge rounded-pill text-bg-vhpteal',
        // Per-filter-type pill colour, e.g. { 'case-study': 'vhppink-distinct' }.
        // The value is just the VHP colour token; JS builds `text-bg-<token>`.
        // Falls back to `badgeClass` for any type not listed here.
        filterColors: options.filterColors || {},
        initTooltips: options.initTooltips !== undefined ? options.initTooltips : true,
        tooltipSelector: options.tooltipSelector || '[data-bs-toggle="tooltip"]',
        showFilterPanel: options.showFilterPanel || false,
        onFormSubmit: options.onFormSubmit || null // Optional callback before form submission
      };

      // Get DOM elements
      this.elements = {
        form: document.getElementById(this.config.formElementIds.form),
        filterToggle: document.getElementById(this.config.formElementIds.filterToggle),
        filterPanel: document.getElementById(this.config.formElementIds.filterPanel),
        applyBtn: document.getElementById(this.config.formElementIds.applyBtn),
        clearBtn: document.getElementById(this.config.formElementIds.clearBtn),
        filterTags: document.getElementById(this.config.formElementIds.filterTags),
        selectedFiltersContainer: document.getElementById(this.config.formElementIds.selectedFilters)
      };

      // Validate required elements exist
      if (!this.elements.form) {
        console.error('[SearchFilter] Form element not found:', this.config.formElementIds.form);
        return;
      }

      // Initialize selected filters
      this.initializeFilters();

      // Set up event listeners
      this.setupEventListeners();

      // Initialize tooltips if enabled
      if (this.config.initTooltips) {
        this.initializeTooltips();
      }

      // Show filter panel if filters are active, OR if the previous navigation
      // was a Clear (sessionStorage flag set in clearFilters); restoring the
      // panel lets the user pick different filters without re-opening it.
      let shouldShowPanel = this.config.showFilterPanel;
      try {
        if (sessionStorage.getItem('vhp-filter-panel-open') === '1') {
          shouldShowPanel = true;
          sessionStorage.removeItem('vhp-filter-panel-open');
        }
      } catch (e) { /* sessionStorage unavailable (e.g. private mode) */ }
      if (shouldShowPanel && this.elements.filterPanel) {
        this.elements.filterPanel.style.display = 'block';
      }

      // Update display
      this.refreshConditionalItems();
    },

    /**
     * Initialize filter selections from server-provided values
     */
    initializeFilters() {
      this.config.filterTypes.forEach(type => {
        const initialValue = this.config.initialFilters[type];
        
        if (this.config.multiSelect) {
          // Multi-select: expect array
          this.selectedFilters[type] = Array.isArray(initialValue) ? [...initialValue] : 
                                        (initialValue ? [initialValue] : []);
        } else {
          // Single select: expect string
          this.selectedFilters[type] = initialValue || '';
        }
      });
    },

    /**
     * Set up event listeners for filter interactions
     */
    setupEventListeners() {
      // Filter toggle button
      if (this.elements.filterToggle && this.elements.filterPanel) {
        this.elements.filterToggle.addEventListener('click', () => {
          const isVisible = this.elements.filterPanel.style.display !== 'none';
          this.elements.filterPanel.style.display = isVisible ? 'none' : 'block';
        });
      }

      // Dropdown item clicks. Let the click bubble so Bootstrap's auto-close
      // handler fires — the dropdown closes after each selection, and the user
      // re-opens it to add more. Pills below show what's already selected.
      document.querySelectorAll('.dropdown-item[data-filter-type]').forEach(item => {
        item.addEventListener('click', (e) => {
          e.preventDefault();

          const filterType = item.dataset.filterType;
          const filterValue = item.dataset.filterValue;

          if (filterType && filterValue) {
            if (this.config.multiSelect) {
              this.toggleFilter(filterType, filterValue);
            } else {
              this.setFilter(filterType, filterValue);
            }
          }
        });
      });

      // Apply filter button
      if (this.elements.applyBtn) {
        this.elements.applyBtn.addEventListener('click', (e) => {
          e.preventDefault();
          this.applyFilters();
        });
      }

      // Form submission handler
      if (this.elements.form) {
        this.elements.form.addEventListener('submit', (e) => {
          e.preventDefault();
          this.applyFilters();
        });
      }

      // Clear filter button
      if (this.elements.clearBtn) {
        this.elements.clearBtn.addEventListener('click', () => {
          this.clearFilters();
        });
      }

      // Make removeFilter accessible globally for onclick handlers in badges
      window.removeFilterTag = (type, value) => {
        if (this.config.multiSelect) {
          this.removeFilterMulti(type, value);
        } else {
          this.removeFilterSingle(type);
        }
      };
    },

    /**
     * Initialize Bootstrap tooltips
     */
    initializeTooltips() {
      if (typeof bootstrap === 'undefined' || !bootstrap.Tooltip) {
        console.warn('[SearchFilter] Bootstrap Tooltip not available');
        return;
      }

      const tooltipElements = document.querySelectorAll(this.config.tooltipSelector);
      tooltipElements.forEach(el => {
        // Validate title attribute
        const title = el.getAttribute('data-bs-title') || el.getAttribute('title');
        if (title && title.trim() !== '' && title !== 'None' && title !== 'null') {
          bootstrap.Tooltip.getOrCreateInstance(el);
        }
      });
    },

    /**
     * Set a single filter (single-select mode)
     */
    setFilter(type, value) {
      if (!this.selectedFilters.hasOwnProperty(type)) return;
      this.selectedFilters[type] = value;
      this.refreshConditionalItems();
    },

    /**
     * Remove a single filter (single-select mode)
     */
    removeFilterSingle(type) {
      if (!this.selectedFilters.hasOwnProperty(type)) return;
      this.selectedFilters[type] = '';
      this.refreshConditionalItems();
    },

    /**
     * Toggle a filter on/off (multi-select mode)
     */
    toggleFilter(type, value) {
      if (!this.selectedFilters.hasOwnProperty(type)) return;
      
      const index = this.selectedFilters[type].indexOf(value);
      if (index > -1) {
        this.selectedFilters[type].splice(index, 1);
      } else {
        this.selectedFilters[type].push(value);
      }
      
      this.refreshConditionalItems();
      this.updateDropdownVisuals();
    },

    /**
     * Remove a specific filter value (multi-select mode)
     */
    removeFilterMulti(type, value) {
      if (!this.selectedFilters.hasOwnProperty(type)) return;
      
      const index = this.selectedFilters[type].indexOf(value);
      if (index > -1) {
        this.selectedFilters[type].splice(index, 1);
      }
      
      this.refreshConditionalItems();
      this.updateDropdownVisuals();
    },

    /**
     * Update visual indication of selected items in dropdowns (multi-select)
     */
    updateDropdownVisuals() {
      if (!this.config.multiSelect) return;

      document.querySelectorAll('.dropdown-item[data-filter-type]').forEach(item => {
        const filterType = item.dataset.filterType;
        const filterValue = item.dataset.filterValue;
        const isActive =
          this.selectedFilters[filterType] &&
          this.selectedFilters[filterType].includes(filterValue);

        // Active state colour matches the filter's own pill/button colour
        // via Bootstrap's `text-bg-<token>` utility (handles contrast text
        // automatically). Falls back to plain `.active` when no colour token
        // is configured for this filter type.
        const colorToken = this.config.filterColors[filterType];
        const colorClass = colorToken ? `text-bg-${colorToken}` : null;

        if (isActive) {
          item.classList.add('active');
          if (colorClass) item.classList.add(colorClass);
        } else {
          item.classList.remove('active');
          if (colorClass) item.classList.remove(colorClass);
        }
      });
    },

    /**
     * Update the filter display with selected tags
     */
    updateFilterDisplay() {
      if (!this.elements.filterTags || !this.elements.selectedFiltersContainer) return;

      // Clear current tags
      this.elements.filterTags.innerHTML = '';

      // Count active filters
      const totalFilters = this.countActiveFilters();

      // Show/hide container
      if (totalFilters === 0) {
        this.elements.selectedFiltersContainer.style.display = 'none';
        return;
      }

      this.elements.selectedFiltersContainer.style.display = 'flex';

      // Create tags for each filter type
      this.config.filterTypes.forEach(type => {
        if (this.config.multiSelect) {
          // Multi-select: show each value as separate tag
          this.selectedFilters[type].forEach(value => {
            this.createFilterTag(type, value);
          });
        } else {
          // Single-select: show one tag per type
          if (this.selectedFilters[type]) {
            this.createFilterTag(type, this.selectedFilters[type]);
          }
        }
      });
    },

    /**
     * Count the total number of active filters
     */
    countActiveFilters() {
      if (this.config.multiSelect) {
        return this.config.filterTypes.reduce((count, type) => {
          return count + (this.selectedFilters[type]?.length || 0);
        }, 0);
      } else {
        return this.config.filterTypes.reduce((count, type) => {
          return count + (this.selectedFilters[type] ? 1 : 0);
        }, 0);
      }
    },

    /**
     * Create a filter tag badge
     */
    createFilterTag(type, value) {
      const tag = document.createElement('span');
      const colorToken = this.config.filterColors[type];
      const baseClass = colorToken
        ? `badge rounded-pill text-bg-${colorToken}`
        : this.config.badgeClass;
      // `mw-100` caps the pill at its container's width so a long
       // "Label: value" string wraps inside the pill instead of overflowing
       // the form-control. `lh-sm` overrides badge's default line-height: 1,
       // which crams wrapped lines together.
      tag.className = `${baseClass} d-inline-flex align-items-center text-wrap mw-100 lh-sm`;
      
      const label = this.config.filterLabels[type] || type;
      tag.textContent = `${label}: ${value}`;

      // type="button" is critical: the badge sits inside the search form, and
      // <button> defaults to type="submit", which would submit the form with
      // the *old* hidden-input values (before applyFilters has written the
      // new state in), making the X click look like a no-op page reload.
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn-close btn-close-white ms-2';
      button.setAttribute('aria-label', 'Remove filter');
      button.addEventListener('click', () => {
        if (this.config.multiSelect) {
          window.removeFilterTag(type, value);
        } else {
          window.removeFilterTag(type);
        }
      });
      tag.appendChild(button);
      
      this.elements.filterTags.appendChild(tag);
    },

    /**
     * Apply filters by updating form fields and submitting
     */
    applyFilters() {
      if (this.config.multiSelect && this.config.multipleInputs) {
        // Multi-select with multiple inputs mode: create separate input for each value
        this.applyFiltersMultipleInputs();
      } else {
        // Standard mode: update hidden form fields
        Object.keys(this.config.filterFieldMap).forEach(filterType => {
          const fieldId = this.config.filterFieldMap[filterType];
          const fieldElement = document.getElementById(fieldId);
          
          if (fieldElement) {
            if (this.config.multiSelect) {
              // Multi-select: join values with commas
              fieldElement.value = this.selectedFilters[filterType]?.join(',') || '';
            } else {
              // Single-select: set value directly
              fieldElement.value = this.selectedFilters[filterType] || '';
            }
          }
        });
      }

      // Show a small inline spinner inside the search bar so users see
      // *something* during the 1-5s server round-trip. With ~10-20 users/month
      // the result cache rarely hits, so most submits are cold-path.
      this.showLoadingIndicator();

      // Submit the form
      this.elements.form.submit();
    },

    /**
     * Swap the Search submit button's content to a Bootstrap spinner +
     * "Searching…" label and disable it. Standard Bootstrap pattern -- no
     * absolute positioning, no overlay, no template changes. The page is
     * about to navigate, so the original button content is restored on its
     * own when the new HTML replaces the document.
     */
    showLoadingIndicator() {
      if (!this.elements.form) return;
      const submitBtn = this.elements.form.querySelector('button[type="submit"]');
      if (!submitBtn || submitBtn.dataset.vhpLoading === '1') return;
      // Lock the button's current size so swapping its content for the
      // (narrower) spinner doesn't cause a layout shift.
      const rect = submitBtn.getBoundingClientRect();
      submitBtn.style.width = `${rect.width}px`;
      submitBtn.style.height = `${rect.height}px`;
      submitBtn.dataset.vhpLoading = '1';
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm align-middle" role="status" aria-hidden="true"></span>' +
        '<span class="visually-hidden">Searching…</span>';
    },

    /**
     * Apply filters using multiple hidden inputs (expects repeated params)
     */
    applyFiltersMultipleInputs() {
      // Remove existing dynamic filter inputs
      Object.values(this.config.filterFieldMap).forEach(paramName => {
        document.querySelectorAll(`input[name="${paramName}"]:not([id])`).forEach(input => {
          input.remove();
        });
        
        // Also remove template hidden inputs
        const templateInput = document.getElementById(this.getFieldId(paramName));
        if (templateInput) {
          templateInput.remove();
        }
      });

      // Create new hidden inputs for each selected value
      Object.keys(this.config.filterFieldMap).forEach(filterType => {
        const paramName = this.config.filterFieldMap[filterType];
        const values = this.selectedFilters[filterType] || [];
        
        values.forEach(value => {
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = paramName;
          input.value = value;
          this.elements.form.appendChild(input);
        });
      });
    },

    /**
     * Get field ID from filter field map
     */
    getFieldId(paramName) {
      for (const [filterType, fieldParam] of Object.entries(this.config.filterFieldMap)) {
        if (fieldParam === paramName) {
          // Try to find corresponding element ID from formElementIds or construct it
          return `filter_${paramName}`;
        }
      }
      return null;
    },

    /**
     * Refresh visibility of dependent filter items based on currently-selected
     * parent filter values. Generic: any item carrying `data-applies-to-<kind>`
     * is shown only when at least one currently-selected item has a matching
     * `data-<kind>` value (or when no item with `data-<kind>` is selected at
     * all — i.e. no parent restriction). Items that become hidden while
     * selected are auto-deselected so they don't leak into the next submit.
     * Driven purely by data attributes; no filter-type pairing baked into JS.
     */
    refreshConditionalItems() {
      const allItems = document.querySelectorAll('.dropdown-item[data-filter-type]');

      // 1) Discover which "kinds" any dependent items rely on.
      const kinds = new Set();
      allItems.forEach(item => {
        for (const attr of item.attributes) {
          if (attr.name.startsWith('data-applies-to-')) {
            kinds.add(attr.name.slice('data-applies-to-'.length));
          }
        }
      });

      // 2) For each kind, collect the set of values for which a parent item is
      // currently selected.
      const parentSelections = {};
      kinds.forEach(k => { parentSelections[k] = new Set(); });
      allItems.forEach(item => {
        const type = item.dataset.filterType;
        const val = item.dataset.filterValue;
        const sel = this.selectedFilters[type];
        const isSelected = Array.isArray(sel) ? sel.includes(val) : sel === val;
        if (!isSelected) return;
        kinds.forEach(k => {
          const v = item.getAttribute(`data-${k}`);
          if (v) parentSelections[k].add(v);
        });
      });

      // 3) Apply visibility + auto-deselect items hidden while selected.
      allItems.forEach(item => {
        let visible = true;
        for (const attr of item.attributes) {
          if (!attr.name.startsWith('data-applies-to-')) continue;
          const kind = attr.name.slice('data-applies-to-'.length);
          const required = attr.value;
          if (!required) continue;             // empty dependency = no restriction
          const sel = parentSelections[kind];
          if (!sel || sel.size === 0) continue; // no parent of this kind selected
          if (!sel.has(required)) { visible = false; break; }
        }
        item.parentElement.style.display = visible ? '' : 'none';
        if (!visible) {
          const type = item.dataset.filterType;
          const val = item.dataset.filterValue;
          const cur = this.selectedFilters[type];
          if (Array.isArray(cur)) {
            const idx = cur.indexOf(val);
            if (idx > -1) cur.splice(idx, 1);
          } else if (cur === val) {
            this.selectedFilters[type] = '';
          }
        }
      });

      // 4) Reflect any state changes in the badge/dropdown UI.
      this.updateFilterDisplay();
      if (this.config.multiSelect) this.updateDropdownVisuals();
    },

    /**
     * Clear all filters
     */
    clearFilters() {
      // Track whether any filter was actually set, so we only trigger a
      // navigation when there's something to clear (idempotent otherwise).
      const hadAny = this.config.filterTypes.some(type => {
        const v = this.selectedFilters[type];
        return Array.isArray(v) ? v.length > 0 : !!v;
      });

      // Reset all filters
      this.config.filterTypes.forEach(type => {
        if (this.config.multiSelect) {
          this.selectedFilters[type] = [];
        } else {
          this.selectedFilters[type] = '';
        }
      });

      this.refreshConditionalItems();

      if (this.config.multiSelect) {
        this.updateDropdownVisuals();
      }

      // Re-apply with the (now empty) filters so the page navigates to a
      // clean state. Mirrors the Apply button's behaviour so Clear is a
      // single user action instead of clear-then-apply. Persist a
      // "panel was open" flag in sessionStorage so the new page restores it
      // (otherwise the user can't pick different filters without re-opening
      // the panel). On the no-op path (nothing was set), just close the
      // panel as a soft UI hint.
      if (hadAny) {
        try { sessionStorage.setItem('vhp-filter-panel-open', '1'); } catch (e) {}
        this.applyFilters();
      } else if (this.elements.filterPanel) {
        this.elements.filterPanel.style.display = 'none';
      }
    }
  };

  // Export to global scope
  window.SearchFilter = SearchFilter;

})(window);
