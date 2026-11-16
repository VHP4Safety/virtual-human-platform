/**
 * Metadata Modal Module
 * Provides reusable functionality for displaying markdown metadata in a Bootstrap modal
 * 
 * Requirements:
 * - Bootstrap 5 (for Modal component)
 * - marked.js library (for markdown parsing)
 * 
 * HTML Structure Required:
 * - Modal with id="metadataModal"
 * - Element with id="metadataModalLabel" (modal title)
 * - Element with id="metadata-loading" (loading spinner)
 * - Element with id="metadata-error" (error message container)
 * - Element with id="metadata-content" (content container)
 * 
 * Usage:
 * MetadataModal.show(url, itemName);
 * MetadataModal.download(); // Downloads the currently displayed metadata
 */

(function(window) {
  'use strict';

  const MetadataModal = {
    currentMetadataUrl: '',
    modalInstance: null,
    elements: null,

    /**
     * Initialize the metadata modal (optional - will auto-initialize on first use)
     */
    init() {
      if (this.elements) return; // Already initialized

      this.elements = {
        modal: document.getElementById('metadataModal'),
        modalTitle: document.getElementById('metadataModalLabel'),
        loadingSpinner: document.getElementById('metadata-loading'),
        errorMessage: document.getElementById('metadata-error'),
        metadataContent: document.getElementById('metadata-content')
      };

      // Validate required elements
      const missing = [];
      Object.entries(this.elements).forEach(([key, element]) => {
        if (!element) missing.push(key);
      });

      if (missing.length > 0) {
        console.error('[MetadataModal] Missing required elements:', missing.join(', '));
        return false;
      }

      return true;
    },

    /**
     * Show metadata in modal
     * @param {string} url - URL to fetch markdown metadata from
     * @param {string} itemName - Name of the item (for modal title)
     */
    async show(url, itemName) {
      // Initialize if not already done
      if (!this.elements && !this.init()) {
        console.error('[MetadataModal] Cannot show modal - initialization failed');
        return;
      }

      this.currentMetadataUrl = url;

      // Create modal instance if needed
      if (!this.modalInstance) {
        this.modalInstance = new bootstrap.Modal(this.elements.modal);
      }

      // Update modal title
      this.elements.modalTitle.textContent = `Metadata - ${itemName}`;

      // Show loading state
      this.showLoading();

      // Open modal
      this.modalInstance.show();

      // Fetch and display metadata
      await this.fetchAndDisplay(url);
    },

    /**
     * Show loading state
     */
    showLoading() {
      this.elements.loadingSpinner.style.display = 'block';
      this.elements.metadataContent.style.display = 'none';
      this.elements.errorMessage.style.display = 'none';
    },

    /**
     * Show content state
     */
    showContent() {
      this.elements.loadingSpinner.style.display = 'none';
      this.elements.metadataContent.style.display = 'block';
      this.elements.errorMessage.style.display = 'none';
    },

    /**
     * Show error state
     */
    showError(message) {
      this.elements.loadingSpinner.style.display = 'none';
      this.elements.metadataContent.style.display = 'none';
      this.elements.errorMessage.style.display = 'block';
      this.elements.errorMessage.textContent = message || 'Failed to load metadata. Please try downloading instead.';
    },

    /**
     * Fetch and display metadata content
     */
    async fetchAndDisplay(url) {
      try {
        const response = await fetch(url);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Get the markdown text
        const markdownText = await response.text();

        // Check if marked.js and DOMPurify are available
        if (typeof marked === 'undefined' || typeof DOMPurify === 'undefined') {
          console.error('[MetadataModal] marked.js or DOMPurify not found');
          throw new Error('Markdown parser not available');
        }

        // Parse markdown to HTML using marked.js; scripts and event handlers are removed
        const htmlContent = DOMPurify.sanitize(marked.parse(markdownText));

        // Display rendered HTML
        this.elements.metadataContent.innerHTML = htmlContent;

        // Add Bootstrap img-fluid class to all images for responsive sizing
        this.elements.metadataContent.querySelectorAll('img').forEach(img => {
          img.classList.add('img-fluid');
        });

        this.showContent();

      } catch (error) {
        console.error('[MetadataModal] Error fetching metadata:', error);
        this.showError();
      }
    },

    /**
     * Download the currently displayed metadata
     */
    download() {
      if (this.currentMetadataUrl) {
        window.open(this.currentMetadataUrl, '_blank');
      } else {
        console.warn('[MetadataModal] No metadata URL available for download');
      }
    },

    /**
     * Hide/close the modal
     */
    hide() {
      if (this.modalInstance) {
        this.modalInstance.hide();
      }
    }
  };

  // Export to global scope
  window.MetadataModal = MetadataModal;

  // Make convenience functions available globally for onclick handlers
  window.showMetadata = (url, itemName) => MetadataModal.show(url, itemName);
  window.downloadMetadata = () => MetadataModal.download();

})(window);
