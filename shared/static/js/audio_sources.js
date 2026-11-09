// Audio sources supply a player with tracks. This one reads recorded chapters from the
// shared audio API. Both apps use it: a book plays as soon as it has recordings.
export class RecordedBookSource {
    // book: { id, slug, title, author, cover? }, audioApi: URL of {chapters: [...]}, place: PlaceKeeper
    constructor({ audioApi, book, place }) {
        this.audioApi = audioApi;
        this.book = book;
        this.place = place;
        this.tracks = [];
        this.loading = null;
    }

    load() {
        this.loading ||= this.fetchTracks();
        return this.loading;
    }

    async fetchTracks() {
        let chapters = [];
        try {
            const response = await fetch(withBasePath(this.audioApi), { credentials: 'include' });
            const data = response.ok && (response.headers.get('content-type') || '').includes('json') ? await response.json() : null;
            chapters = data?.chapters || [];
        } catch (_) { chapters = []; }
        const { book } = this;
        this.tracks = chapters.map(chapter => ({
            id: chapter.chapter_id, bookId: book.id, bookTitle: book.title, author: book.author || '', cover: book.cover || null,
            title: chapter.title, urls: [chapter.url], durationMs: chapter.duration_ms, timings: chapter.timings,
        }));
        return this.tracks;
    }
}
