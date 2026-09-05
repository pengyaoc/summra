/**
 * BlogPost Component
 * Displays an individual blog post with markdown rendering
 */

class BlogPost {
    constructor(app) {
        this.app = app;
        this.post = null;
    }

    async render(slug) {
        // Fetch blog post
        await this.loadPost(slug);

        // Get container
        const container = document.getElementById('blog-post-container');
        if (!container) return;

        // Handle post not found
        if (!this.post) {
            container.innerHTML = `
                <div class="blog-error">
                    <h2>Blog post not found</h2>
                    <p>The blog post you're looking for doesn't exist.</p>
                    <a href="${withBasePath('/blog')}" class="blog-back-link">← Back to blog</a>
                </div>
            `;
            return;
        }

        // Format date
        const date = this.formatDate(this.post.published_date || this.post.created_at);
        const author = this.post.author || 'Summra Team';

        // Render markdown content (strip first H1 since we show title in header)
        let content = this.post.content;
        // Remove first H1 heading if it exists
        content = content.replace(/^#\s+.+$/m, '').trim();

        // Remove SEO keywords section (everything after "---" followed by "**SEO Keywords:**" or "**Keywords:**")
        content = content.replace(/---\s*\n\s*\*\*(?:SEO )?Keywords:\*\*.*$/s, '').trim();

        const contentHTML = this.app.renderMarkdown(content);

        // Add header image if available
        const headerImageHTML = this.post.header_image_url ? `
            <div class="blog-post-header-image">
                <img src="${this.app.escapeHtml(this.post.header_image_url)}"
                     alt="${this.app.escapeHtml(this.post.title)}"
                     loading="eager">
            </div>
        ` : '';

        // Render post (no "Back to blog" button - breadcrumb handles navigation)
        container.innerHTML = `
            <article class="blog-post">
                ${headerImageHTML}
                <header class="blog-post-header">
                    <h1 class="blog-post-title">${this.app.escapeHtml(this.post.title)}</h1>
                    <div class="blog-post-meta">
                        <span class="blog-post-author">${this.app.escapeHtml(author)}</span>
                        <span class="blog-post-date">${date}</span>
                    </div>
                </header>
                <div class="blog-post-content">
                    ${contentHTML}
                </div>
            </article>
        `;

        // Update page title and breadcrumb with actual post title
        this.app.updatePageTitle(`${this.post.title} | Summra Blog`);
        this.app.currentBlogPost = this.post;
        this.app.updateBreadcrumbs('blog-post');

        // Scroll to top
        window.scrollTo(0, 0);
    }

    async loadPost(slug) {
        try {
            const response = await fetch(withBasePath(`/api/blog/${slug}`));
            const data = await response.json();

            if (data.success) {
                this.post = data.post;
            } else {
                console.error('Failed to load blog post:', data.error);
                this.post = null;
            }
        } catch (error) {
            console.error('Error loading blog post:', error);
            this.post = null;
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
window.BlogPost = BlogPost;
