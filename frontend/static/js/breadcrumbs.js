// Breadcrumb trail: build/render/show/hide the per-section breadcrumb nav.
//
// Uses the global currentAppPath()/parseAppRoute() from route_utils.js
// (loaded as a plain <script> before app.js, not `import`ed — see that
// file's header comment) — undeclared bare names in an ES module still
// resolve against the global/window scope exactly as in a classic script,
// so this works as long as route_utils.js runs first, which it already
// does in index.html's script order.
//
// Extracted from app.js's single SummraApp class (2026-09 refactor) as a
// plain object of methods, merged onto SummraApp.prototype via
// Object.assign in app.js — see pagination.js's header comment and
// frontend/static/js/README.md for the pattern.
export const breadcrumbsMixin = {
    buildBreadcrumbs() {
        const breadcrumbs = [
            { name: 'Home', url: '/', position: 1 }
        ];

        const path = currentAppPath();

        // Parse different page types (shared with handleRoute() via
        // parseAppRoute — see route_utils.js)
        const {
            bookMatch, mediumMatch: summaryMatch, chapterMatch, categoryMatch,
            categoriesMatch, allBooksMatch, discoverMatch, blogMatch,
            blogPostMatch, authorMatch
        } = parseAppRoute(path);

        if (discoverMatch) {
            breadcrumbs.push({ name: 'Discover', url: '/discover', position: 2 });
        } else if (authorMatch) {
            const authorName = this.currentAuthor?.name || decodeURIComponent(authorMatch[1]).replace(/-/g, ' ');
            breadcrumbs.push({ name: authorName, url: path, position: 2 });
        } else if (blogPostMatch) {
            breadcrumbs.push({ name: 'Blog', url: '/blog', position: 2 });
            const postName = this.currentBlogPost?.title || 'Post';
            breadcrumbs.push({ name: postName, url: path, position: 3 });
        } else if (blogMatch) {
            breadcrumbs.push({ name: 'Blog', url: '/blog', position: 2 });
        } else if (categoriesMatch) {
            breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
        } else if (categoryMatch) {
            breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
            // Get category name from current data if available
            const categoryId = parseInt(categoryMatch[1]);
            const categoryName = this.currentCategory?.name || `Category ${categoryId}`; // Fallback to ID if name not available
            breadcrumbs.push({ name: categoryName, url: `/categories/${categoryId}`, position: 3 });
        } else if (allBooksMatch) {
            breadcrumbs.push({ name: 'All Books', url: '/books', position: 2 });
        } else if (this.currentBook) {
            // Use origin category if user came from a category page
            if (this.originCategory) {
                breadcrumbs.push({ name: 'Categories', url: '/categories', position: 2 });
                breadcrumbs.push({
                    name: this.originCategory.name,
                    url: `/categories/${this.originCategory.id}`,
                    position: 3
                });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 4
                });
            }
            // Use Discover if user came from Discover page
            else if (this.originDiscover) {
                breadcrumbs.push({ name: 'Discover', url: '/discover', position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }
            // Use Author if user came from Author page
            else if (this.originAuthor) {
                breadcrumbs.push({ name: this.originAuthor.name, url: `/authors/${this.originAuthor.slug}`, position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }
            // Otherwise use All Books
            else {
                breadcrumbs.push({ name: 'All Books', url: '/books', position: 2 });
                breadcrumbs.push({
                    name: this.currentBook.title,
                    url: `/books/${this.slugify(this.currentBook.title)}`,
                    position: 3
                });
            }

            if (summaryMatch) {
                breadcrumbs.push({ name: 'Summary', url: path, position: breadcrumbs.length + 1 });
            } else if (chapterMatch) {
                const chapterNum = parseInt(chapterMatch[2]);
                // Try to find the chapter in the loaded chapters to get the title
                const chapter = this.chapters.find(c => c.chapter_number === chapterNum);
                const chapterTitle = chapter?.chapter_title || null;
                const chapterName = chapterTitle
                    ? `${chapterNum}. ${chapterTitle}`
                    : `Chapter ${chapterNum}`;
                breadcrumbs.push({
                    name: chapterName,
                    url: path,
                    position: breadcrumbs.length + 1
                });
            }
        }

        return breadcrumbs;
    },

    /**
     * Hide all breadcrumb navigations
     */
    hideAllBreadcrumbs(except = null) {
        // `except` lets a caller skip the section it is about to immediately
        // re-render, which avoids a visible flash (display:none collapses the
        // breadcrumb's layout box; the content below jumps up then back down
        // when the rebuilt HTML reattaches a frame later). See updateBreadcrumbs.
        const sections = ['book', 'medium', 'chapter', 'category', 'all-categories', 'blog', 'blog-post', 'author'];
        sections.forEach(section => {
            if (section === except) return;
            const breadcrumbNav = document.getElementById(`breadcrumb-nav-${section}`);
            if (breadcrumbNav) {
                breadcrumbNav.classList.add('hidden');
            }
        });
    },

    /**
     * Render breadcrumbs in the navigation
     * @param {Array} breadcrumbs - Array of breadcrumb objects
     * @param {string} section - Section identifier (book, medium, chapter, category, all-categories)
     */
    renderBreadcrumbs(breadcrumbs, section = 'book') {
        const breadcrumbNav = document.getElementById(`breadcrumb-nav-${section}`);
        const breadcrumbList = document.getElementById(`breadcrumb-list-${section}`);

        if (!breadcrumbNav || !breadcrumbList) return;

        // Hide breadcrumbs on home page
        if (breadcrumbs.length <= 1) {
            breadcrumbNav.classList.add('hidden');
            return;
        }

        // Show breadcrumbs
        breadcrumbNav.classList.remove('hidden');

        // Build breadcrumb HTML
        const breadcrumbHTML = breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1;

            if (isLast) {
                // Last item - current page (no link)
                return `
                    <li class="breadcrumb-item">
                        <span class="breadcrumb-current">${this.escapeHtml(crumb.name)}</span>
                    </li>
                `;
            } else {
                // Intermediate items - with links
                return `
                    <li class="breadcrumb-item">
                        <a href="${withBasePath(crumb.url)}" class="breadcrumb-link">${this.escapeHtml(crumb.name)}</a>
                        <span class="breadcrumb-separator">›</span>
                    </li>
                `;
            }
        }).join('');

        breadcrumbList.innerHTML = breadcrumbHTML;
    },

    /**
     * Update breadcrumbs based on current page
     * @param {string} section - Section identifier (book, medium, chapter, category, all-categories)
     */
    updateBreadcrumbs(section = 'book') {
        // Hide every OTHER section's breadcrumb (they may be leftover-visible
        // from a prior view). Do NOT hide the one we're about to render —
        // hiding it would collapse its layout box, jump the page content, then
        // the rebuild a frame later jumps it back ("snap-in" regression).
        this.hideAllBreadcrumbs(section);

        // Build and render breadcrumbs for the active section
        const breadcrumbs = this.buildBreadcrumbs();
        this.renderBreadcrumbs(breadcrumbs, section);
    }

};
