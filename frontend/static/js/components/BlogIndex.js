/**
 * BlogIndex Component
 * Displays a grid of blog posts with title, excerpt, and "Read more" link
 */

class BlogIndex {
    constructor(app) {
        this.app = app;
        this.posts = [];
    }

    async render() {
        // Fetch all blog posts
        await this.loadPosts();

        // Get container
        const container = document.getElementById('blog-index-container');
        if (!container) return;

        // Render posts grid
        if (this.posts.length === 0) {
            container.innerHTML = `
                <div class="blog-empty">
                    <h2>No blog posts yet</h2>
                    <p>Check back soon for articles about classic literature!</p>
                </div>
            `;
            return;
        }

        // Create grid HTML
        const gridHTML = this.posts.map(post => {
            const date = this.formatDate(post.published_date || post.created_at);
            const excerpt = post.excerpt || 'Read this article to learn more...';

            return `
                <div class="blog-card" data-slug="${this.app.escapeHtml(post.slug)}">
                    <div class="blog-card-content">
                        <h3 class="blog-card-title">${this.app.escapeHtml(post.title)}</h3>
                        <p class="blog-card-date">${date}</p>
                        <p class="blog-card-excerpt">${this.app.escapeHtml(excerpt)}</p>
                        <a href="/blog/${this.app.escapeHtml(post.slug)}" class="blog-card-link">
                            Read more →
                        </a>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div class="blog-grid">
                ${gridHTML}
            </div>
        `;

        // Add click handlers
        container.querySelectorAll('.blog-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // Don't navigate if clicking on the link directly (let the link handle it)
                if (e.target.classList.contains('blog-card-link')) return;

                const slug = card.dataset.slug;
                window.location.href = `/blog/${slug}`;
            });
        });
    }

    async loadPosts() {
        try {
            const response = await fetch('/api/blog');
            const data = await response.json();

            if (data.success) {
                this.posts = data.posts || [];
            } else {
                console.error('Failed to load blog posts:', data.error);
                this.posts = [];
            }
        } catch (error) {
            console.error('Error loading blog posts:', error);
            this.posts = [];
        }
    }

    formatDate(dateString) {
        if (!dateString) return '';

        try {
            const date = new Date(dateString);
            const options = { year: 'numeric', month: 'long', day: 'numeric' };
            return date.toLocaleDateString('en-US', options);
        } catch (error) {
            return dateString;
        }
    }
}

// Export for use in app.js
window.BlogIndex = BlogIndex;
