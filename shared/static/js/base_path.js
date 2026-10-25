// Deploy-time URL prefix helpers, shared by every app and the reader
// platform. Loaded as a plain <script> before any script that builds an
// app-relative URL, and exposed on `window` (window.APP_BASE_PATH is injected
// by the base template from Flask's request.script_root).
(function (root) {
    "use strict";

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

    root.summraBasePath = summraBasePath;
    root.withBasePath = withBasePath;
})(typeof window !== "undefined" ? window : globalThis);
