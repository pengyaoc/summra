// Small helpers the reader platform mixins share: HTML escaping and lookups
// into window.READER_CONFIG (ReaderConfig.to_client(), rendered by the app's
// page template). Merged onto the host app's prototype by platform.js.
export const readerUtilsMixin = {
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    readerConfig() {
        return window.READER_CONFIG;
    },

    readerMode(id) {
        return this.readerConfig().modes.find(mode => mode.id === id) || null;
    },

    readerLayout(id) {
        return this.readerMode(id)?.layout === 'side_by_side' ? 'side_by_side' : 'single';
    },

    // Configured modes, in config order, that this book's manifest offers and
    // that fit the current screen.
    readerAvailableModes(manifest) {
        return this.readerConfig().modes.map(mode => mode.id).filter(id =>
            manifest.modes.some(item => item.mode === id && item.availability !== 'unavailable') &&
            this.isContinuousReaderModeAvailable(id));
    },
};
