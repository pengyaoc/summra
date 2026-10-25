// The shared web reader: an app plugs in by calling applyReaderPlatform(Host)
// on its app class. Every mixin is a plain object of methods merged onto
// Host.prototype, so methods keep reading/writing `this.*` as before.
// The only file here that imports: the mixins are also loaded alone in tests.
import { readerUtilsMixin } from './reader_utils.js';
import { paginationMixin, createPaginationState } from './pagination.js';
import { settingsMixin } from './settings.js';
import { continuousReaderMixin } from './continuous_reader.js';
import { blocksMixin } from './blocks.js';

export { createPaginationState };

// Filled in only when the host has no method of its own.
const readerPlatformDefaults = {
    showOnlySections() {},

    initReaderPlatform() {
        this.apiBase = withBasePath(this.readerConfig().api_base);
        this.pagination = createPaginationState();
    },
};

export function applyReaderPlatform(Host) {
    Object.assign(Host.prototype, readerUtilsMixin, paginationMixin, settingsMixin, continuousReaderMixin, blocksMixin);
    for (const [key, method] of Object.entries(readerPlatformDefaults)) {
        if (!(key in Host.prototype)) Host.prototype[key] = method;
    }
}
