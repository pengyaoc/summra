// Pure route-parsing helpers shared by handleRoute() and buildBreadcrumbs()
// in app.js — and withBasePath(), used by every module that builds an
// app-relative URL (fetch calls, hrefs). Loaded as a plain <script> before
// app.js (and before components/BlogIndex.js, components/BlogPost.js, which
// need withBasePath too) and exposed on `window`, same pattern as
// view_mode.js.
//
// Bug this fixes: handleRoute() stripped the deploy-time base path
// (window.APP_BASE_PATH, e.g. "/summrabook") from window.location.pathname
// before matching routes, but buildBreadcrumbs() read the raw pathname —
// so under a base-path deployment every breadcrumb regex failed to match
// and breadcrumbs silently collapsed to just "Home". Centralizing both the
// base-path strip (stripBasePath/currentAppPath) and the route regexes
// (parseAppRoute) means there is exactly one place each can go stale.
//
// Also fixes a second, smaller divergence: buildBreadcrumbs()'s authorMatch
// regex was `[^\/]+` (no slashes) while handleRoute()'s and the backend's
// route (`@app.route('/authors/<path:author_slug>')`) both use `.+`
// (slashes allowed) — parseAppRoute now uses the `.+` version everywhere.
(function (root) {
    "use strict";

    function stripBasePath(rawPath, basePath) {
        if (basePath && rawPath.startsWith(basePath)) {
            return rawPath.slice(basePath.length) || '/';
        }
        return rawPath;
    }

    function currentAppPath() {
        const rawPath = root.location.pathname;
        const base = root.APP_BASE_PATH || '';
        return stripBasePath(rawPath, base);
    }

    // Inverse of stripBasePath: prepend the deploy-time base path (e.g.
    // "/summrabook") to an app-relative path, for fetch() calls and hrefs.
    // Leaves absolute/external URLs untouched.
    function summraBasePath() {
        return root.APP_BASE_PATH || '';
    }

    function withBasePath(path) {
        if (!path || path.startsWith('http://') || path.startsWith('https://') || path.startsWith('//')) {
            return path;
        }
        return summraBasePath() + path;
    }

    // Parse an app-relative path (already stripped of any base path) into the
    // route match object shared by handleRoute() and buildBreadcrumbs().
    //
    // Routes:
    //   /books/{slug}                  - Book detail
    //   /books/{slug}/summary          - Medium summary detail
    //   /books/{slug}/chapters/{num}   - Chapter detail
    //   /categories/{id}               - Category detail
    //   /categories                    - All categories view
    //   /books                         - All books grid view
    //   /discover                      - Discover page by difficulty
    //   /authors/{name}                - Author detail
    //   /blog                          - Blog index
    //   /blog/{slug}                   - Blog post
    function parseAppRoute(path) {
        return {
            bookMatch: path.match(/^\/books\/([^\/]+)$/),
            mediumMatch: path.match(/^\/books\/([^\/]+)\/summary$/),
            chapterMatch: path.match(/^\/books\/([^\/]+)\/chapters\/(\d+)$/),
            categoryMatch: path.match(/^\/categories\/(\d+)$/),
            categoriesMatch: path === '/categories',
            allBooksMatch: path === '/books',
            discoverMatch: path === '/discover',
            authorMatch: path.match(/^\/authors\/(.+)$/),
            blogMatch: path === '/blog',
            blogPostMatch: path.match(/^\/blog\/([^\/]+)$/),
        };
    }

    root.stripBasePath = stripBasePath;
    root.currentAppPath = currentAppPath;
    root.parseAppRoute = parseAppRoute;
    root.summraBasePath = summraBasePath;
    root.withBasePath = withBasePath;
})(typeof window !== "undefined" ? window : globalThis);
