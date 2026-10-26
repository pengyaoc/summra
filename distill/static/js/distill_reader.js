// Distill's whole web-reader client: two hooks on the shared reader platform, and a boot.
import { applyReaderPlatform } from '../shared/js/platform.js';

class DistillReader {
    classifyUnit(text) { return JSON.parse(text); }
    selectBook(book) { location.assign(withBasePath(`/books/${book.slug}`)); }
}
applyReaderPlatform(DistillReader);

const reader = new DistillReader();
reader.initReaderPlatform();
reader.setupReadingSettings();
reader.loadReadingPreferences();
reader.setupPagination();
await window.authModule.initAuth(); // the shared default module: one memoised checkAuthStatus()
await reader.showContinuousReader(window.DISTILL_BOOK, {
    chapter: new URLSearchParams(location.search).get('chapter'),
});
