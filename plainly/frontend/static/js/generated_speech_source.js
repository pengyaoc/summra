// A player source for Plainly's generated summary speech: one track, in parts that
// the server is still producing as they are needed.
export class GeneratedSpeechSource {
    constructor({ urls, bookId, bookTitle, author, title, audioId, cover, onFinish }) {
        this.audioId = audioId;
        this.onFinish = onFinish;
        this.book = { id: `speech-${bookId}`, title: bookTitle, author };  // never the same book as a reader's recording
        this.place = null;
        this.tracks = [{
            id: audioId, bookId: this.book.id, bookTitle, author, title, urls, cover,
            waitForPart: part => this.waitForChunk(urls[part]),
        }];
    }

    finish() {
        const done = this.onFinish;
        this.onFinish = null;
        done?.();
    }

    async waitForChunk(url, retries = 30) {
        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, { method: 'HEAD' });
                if (response.ok) return true;
            } catch (error) {
                // Chunk not ready yet
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        return false;
    }
}
