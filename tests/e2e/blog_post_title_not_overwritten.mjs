// Regression test: showBlogPost must not overwrite the real post title that
// BlogPost.render() already set via document.title.
//
// Bug: showBlogPost's finishPageTransition() call always passed the generic
// placeholder 'Blog Post | Summra' as the title, which runs AFTER
// blogPost.render(slug) has already called updatePageTitle() with the real
// post title (BlogPost.js) — silently clobbering it back to the placeholder
// on every real blog post view.
//
// Requires FEATURE_BLOG=True on the server under test (the blog routes/UI
// are feature-flagged off by default).
//
// Usage: BASE_URL=http://localhost:5001 node blog_post_title_not_overwritten.mjs

import { chromium } from 'playwright';

const BASE = (process.env.BASE_URL || 'http://localhost:5001').replace(/\/$/, '');

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

let failed = false;
const checks = [];
function check(name, cond, detail = '') {
  checks.push({ name, cond, detail });
  if (!cond) failed = true;
}

try {
  // Find a real blog post slug from the index.
  await page.goto(`${BASE}/blog`, { waitUntil: 'domcontentloaded', timeout: 15_000 });
  await page.waitForFunction(() => window.summraApp && window.summraApp.currentPage === 'blog',
    { timeout: 10_000 });
  await page.waitForTimeout(500);

  const firstPostHref = await page.evaluate(() => {
    const link = document.querySelector('#blog-index-container a[href*="/blog/"]');
    return link ? link.getAttribute('href') : null;
  });
  if (!firstPostHref) {
    throw new Error('No blog post link found on /blog — cannot run this test.');
  }
  const slug = firstPostHref.split('/blog/')[1];

  // Navigate to the post directly via the app's router (not a full page load)
  // to exercise showBlogPost the same way client-side navigation does.
  await page.evaluate(async (s) => {
    await window.summraApp.showBlogPost(s);
  }, slug);
  await page.waitForTimeout(300);

  const title = await page.evaluate(() => document.title);
  const realTitle = await page.evaluate(() =>
    window.summraApp.blogPost && window.summraApp.blogPost.post
      ? window.summraApp.blogPost.post.title
      : null);

  check('a real post was found and rendered', !!realTitle, `realTitle=${realTitle}`);
  check('document.title contains the real post title, not the generic placeholder',
        !!realTitle && title.startsWith(realTitle),
        `actual document.title: ${JSON.stringify(title)}, expected to start with: ${JSON.stringify(realTitle)}`);
  check('document.title is not the generic placeholder',
        title !== 'Blog Post | Summra',
        `actual: ${JSON.stringify(title)}`);
} finally {
  await browser.close();
}

for (const c of checks) {
  const tag = c.cond ? 'PASS' : 'FAIL';
  const suffix = c.detail ? ` — ${c.detail}` : '';
  console.log(`[${tag}] ${c.name}${suffix}`);
}
process.exit(failed ? 1 : 0);
