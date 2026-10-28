/* Kindle e-ink reader (shared/kindle/reader_base.html).
 *
 * Turns the server-rendered chapter into pages with CSS columns: the flow is
 * one viewport tall, each column one page wide, and turning a page moves the
 * flow left by a page. Tap the left third to go back, the rest to go forward,
 * the top band for the menu, as on a Kindle. No animation: every repaint
 * ghosts on e-ink.
 *
 * ES5 only (the older Kindle browser is WebKit 531 / Safari 4): no let/const,
 * arrow functions, the class-list API or Function.prototype.bind.
 */
(function () {
  var doc = document.documentElement;
  var body = document.body;
  var viewport = document.getElementById('viewport');
  var flow = document.getElementById('flow');
  var head = document.getElementById('head');
  var foot = document.getElementById('foot');
  var menu = document.getElementById('menu');
  var end = document.getElementById('chapter-end');
  if (!viewport || !flow) return;

  var GAP = 72;       // space between columns: the side margins of a page
  var WPM = 230;      // reading speed for "min left in chapter"
  var CHARS_PER_WORD = 6;

  function data(name) { return body.getAttribute('data-' + name); }
  function num(name) { return parseInt(data(name), 10) || 0; }
  function byId(id) { return document.getElementById(id); }
  function hasClass(el, c) { return (' ' + el.className + ' ').indexOf(' ' + c + ' ') >= 0; }
  function addClass(el, c) { if (!hasClass(el, c)) el.className = (el.className + ' ' + c).replace(/^\s+/, ''); }
  function removeClass(el, c) {
    el.className = (' ' + el.className + ' ').replace(' ' + c + ' ', ' ').replace(/^\s+|\s+$/g, '');
  }
  function setCookie(name, value) {
    var expires = new Date(new Date().getTime() + 365 * 24 * 3600 * 1000).toUTCString();
    document.cookie = name + '=' + value + '; expires=' + expires + '; path=' + (data('cookie-path') || '/');
  }

  var bookId = data('book');
  var chapter = data('ch');
  var units = [];     // the #flow descendants carrying data-i, in document order
  var all = flow.getElementsByTagName('*');
  for (var u = 0; u < all.length; u++) {
    if (all[u].getAttribute('data-i') !== null) units.push(all[u]);
  }
  var rows = false;   // fallback when columns aren't supported: pages stacked vertically
  var step = 1;       // width (or height) of one page
  var pages = 1;
  var page = 0;
  var starts = [];    // page each paragraph starts on
  var ends = [];      // page each paragraph ends on

  addClass(doc, 'js');

  // Older Kindle WebKit can pan into blank document space even when CSS
  // overflow is hidden. Cancel drags (not taps) across the whole reader,
  // including the gutters and the settings banners. Old engines interpret
  // the options object as capture=true; newer ones also honor passive=false.
  function preventDocumentScroll(e) {
    e = e || window.event;
    if (e.preventDefault) e.preventDefault();
    e.returnValue = false;
  }
  var scrollOptions = { capture: true, passive: false };
  body.addEventListener('touchmove', preventDocumentScroll, scrollOptions);
  body.addEventListener('wheel', preventDocumentScroll, scrollOptions);
  body.addEventListener('mousewheel', preventDocumentScroll, true);

  function resetDocumentScroll() {
    if (window.pageXOffset || window.pageYOffset || doc.scrollTop || doc.scrollLeft || body.scrollTop || body.scrollLeft) {
      window.scrollTo(0, 0);
      doc.scrollTop = doc.scrollLeft = body.scrollTop = body.scrollLeft = 0;
    }
  }
  window.addEventListener('scroll', resetDocumentScroll, false);

  function setStyle(prop, value) {
    var prefixes = ['webkit', 'Moz', ''];
    for (var i = 0; i < prefixes.length; i++) {
      var p = prefixes[i] ? prefixes[i] + prop.charAt(0).toUpperCase() + prop.slice(1) : prop;
      flow.style[p] = value;
    }
  }

  function offsetOf(el) {
    var a = el.getBoundingClientRect();
    var b = flow.getBoundingClientRect();
    return rows ? a.top - b.top : a.left - b.left;
  }

  function pageOf(el) {
    return Math.max(0, Math.floor((offsetOf(el) + 2) / step));
  }

  function layout() {
    viewport.style.top = head.offsetHeight + 'px';
    viewport.style.bottom = foot.offsetHeight + 'px';
    viewport.style.height = '';
    var width = Math.max(1, viewport.clientWidth);
    var height = Math.max(1, viewport.clientHeight);
    // Discard a scroll offset retained by the browser across chapter loads.
    window.scrollTo(0, 0);
    flow.style.left = '0px';
    flow.style.top = '0px';
    rows = false;
    flow.style.width = width + 'px';
    flow.style.height = height + 'px';
    setStyle('columnWidth', width + 'px');
    setStyle('columnGap', GAP + 'px');
    setStyle('columnFill', 'auto');
    step = width + GAP;
    if (flow.scrollHeight > height + 4 && pageOf(end) === 0) {
      // No column support: show the chapter in viewport-tall slices.
      rows = true;
      setStyle('columnWidth', 'auto');
      flow.style.height = 'auto';
      step = height;
      var h = Math.floor(height / lineHeight()) * lineHeight();
      if (h > 0) { step = h; viewport.style.height = h + 'px'; }
    }
    pages = pageOf(end) + 1;
    starts = [];
    ends = [];
    for (var i = 0; i < units.length; i++) {
      starts.push(pageOf(units[i]));
      ends.push(lastPageOf(units[i], starts[i]));
    }
  }

  // Last page a paragraph runs onto: its rightmost (or lowest) line box.
  function lastPageOf(el, first) {
    var rects = el.getClientRects();
    var b = flow.getBoundingClientRect();
    var last = first;
    for (var i = 0; i < rects.length; i++) {
      var off = rows ? rects[i].bottom - b.top - 2 : rects[i].left - b.left + 2;
      last = Math.max(last, Math.floor(off / step));
    }
    return last;
  }

  function lineHeight() {
    var p = flow.getElementsByTagName('p')[0] || flow;
    var lh = parseFloat(window.getComputedStyle(p, null).lineHeight);
    return lh > 0 ? lh : 30;
  }

  // Index (data-i) of the paragraph at the top of the current page.
  function currentParagraph() {
    var last = 0;
    for (var i = 0; i < units.length; i++) {
      var idx = units[i].getAttribute('data-i');
      if (idx === null) continue;
      last = parseInt(idx, 10);
      if (ends[i] >= page) return last;
    }
    return last;
  }

  function pageOfParagraph(index) {
    for (var i = 0; i < units.length; i++) {
      var idx = units[i].getAttribute('data-i');
      if (idx !== null && parseInt(idx, 10) >= index) return starts[i];
    }
    return 0;
  }

  function show(n) {
    page = Math.max(0, Math.min(pages - 1, n));
    if (rows) flow.style.top = (-page * step) + 'px';
    else flow.style.left = (-page * step) + 'px';
    var done = pages > 1 ? page / (pages - 1) : 1;
    var chars = num('chars');
    var pct = Math.floor(100 * (num('before') + chars * done) / Math.max(1, num('total')));
    var minutes = Math.ceil(chars * (1 - done) / CHARS_PER_WORD / WPM);
    byId('left').innerHTML = page === pages - 1 ? 'End of chapter'
      : minutes <= 1 ? '1 min left in chapter' : minutes + ' mins left in chapter';
    byId('right').innerHTML = pct + '%';
    byId('menu-pos').innerHTML = 'Page ' + (page + 1) + ' of ' + pages + ' in this chapter · ' + pct + '% of the book';
    setCookie('kpos_' + bookId, chapter + '.' + currentParagraph());
    setCookie('klast', data('slug'));
    setCookie('ktext', data('text'));
    scheduleSync();
  }

  // Signed in: save each page you settle on to your account, like the web
  // reader, so the website and other devices open at the same place.
  var syncTimer = null;
  var finishTimer = null;
  var forwardTurn = false;
  var pageShownAt = new Date().getTime();

  function sync(paragraph, forward, seconds, finished) {
    var url = data('sync');
    if (!url || !window.XMLHttpRequest || !window.JSON) return;
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', url, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(JSON.stringify({
        book_id: parseInt(bookId, 10), ch: parseInt(chapter, 10), p: paragraph,
        text: data('text'), forward: forward, seconds: seconds, finished: finished
      }));
    } catch (e) { /* best effort: the cookie still has your place */ }
  }

  function lastParagraph() {
    for (var i = units.length - 1; i >= 0; i--) {
      var idx = units[i].getAttribute('data-i');
      if (idx !== null) return parseInt(idx, 10);
    }
    return 0;
  }

  function scheduleSync() {
    if (!data('sync')) return;
    var forward = forwardTurn;
    forwardTurn = false;
    var now = new Date().getTime();
    var seconds = Math.min(60, Math.floor((now - pageShownAt) / 1000));
    pageShownAt = now;
    var paragraph = currentParagraph();
    clearTimeout(syncTimer);
    clearTimeout(finishTimer);
    syncTimer = setTimeout(function () { sync(paragraph, forward, seconds, false); }, 600);
    // Staying on the book's last page after paging to it finishes the book.
    if (forward && page === pages - 1 && !data('next')) {
      finishTimer = setTimeout(function () { sync(lastParagraph(), true, 2, true); }, 2000);
    }
  }

  function next() {
    if (page < pages - 1) { forwardTurn = true; show(page + 1); }
    else if (data('next')) window.location.href = data('next') + '#fwd';
  }

  function prev() {
    if (page > 0) show(page - 1);
    else if (data('prev')) window.location.href = data('prev') + '#end';
  }

  function menuOpen() { return !hasClass(menu, 'hidden'); }
  function openMenu() { removeClass(menu, 'hidden'); resetDocumentScroll(); }
  function closeMenu() { addClass(menu, 'hidden'); resetDocumentScroll(); }

  function currentSize() {
    var m = /\bfs-(\d+)\b/.exec(doc.className);
    return m ? parseInt(m[1], 10) : (num('font-size-default') || 3);
  }

  function updateSizeControls() {
    var size = currentSize();
    var max = num('font-size-max') || 5;
    var status = byId('font-size-status');
    if (status) status.innerHTML = size + ' / ' + max;
    var ids = ['smaller', 'bigger'];
    for (var i = 0; i < ids.length; i++) {
      var button = byId(ids[i]);
      if (!button) continue;
      var disabled = i === 0 ? size === 1 : size === max;
      button.setAttribute('aria-disabled', disabled ? 'true' : 'false');
      if (disabled) addClass(button, 'off');
      else removeClass(button, 'off');
    }
  }

  function resize(delta) {
    var size = currentSize();
    var nextSize = Math.max(1, Math.min(num('font-size-max') || 5, size + delta));
    if (nextSize === size) return;
    var at = currentParagraph();
    doc.className = doc.className.replace(/\bfs-\d+\b/, 'fs-' + nextSize);
    setCookie('kfs', nextSize);
    updateSizeControls();
    layout();
    show(pageOfParagraph(at));
  }

  function changeFont(choice) {
    if (!/^(system|song|hei)$/.test(choice)) return;
    var selected = byId('font-' + choice);
    if (!selected || hasClass(selected, 'on')) return;
    var at = currentParagraph();
    doc.className = doc.className.replace(/\bfont-(system|song|hei)\b/, 'font-' + choice);
    setCookie('kff', choice);
    var choices = ['system', 'song', 'hei'];
    for (var i = 0; i < choices.length; i++) {
      var button = byId('font-' + choices[i]);
      if (button) removeClass(button, 'on');
    }
    addClass(selected, 'on');
    layout();
    show(pageOfParagraph(at));
  }

  function inside(el, container) {
    while (el) { if (el === container) return true; el = el.parentNode; }
    return false;
  }

  function linkOf(el) {
    while (el && el !== body) { if (el.tagName === 'A') return el; el = el.parentNode; }
    return null;
  }

  document.onclick = function (e) {
    e = e || window.event;
    var target = e.target || e.srcElement;
    var link = linkOf(target);
    if (menuOpen()) {
      if (target.id === 'smaller') return resize(-1);
      if (target.id === 'bigger') return resize(1);
      if (target.getAttribute('data-reading-font')) return changeFont(target.getAttribute('data-reading-font'));
      if (link && hasClass(link, 'keep')) {
        // Switching Plain English / Original keeps your paragraph.
        link.href = link.href.split('#')[0] + '#p=' + currentParagraph();
        return true;
      }
      if (link) return true;
      if (target.id === 'close' || target === menu || !inside(target, menu)) closeMenu();
      return false;
    }
    if (link) return true;
    var x = e.clientX;
    var y = e.clientY;
    var w = body.clientWidth || doc.clientWidth;
    var h = body.clientHeight || doc.clientHeight;
    if (y < h * 0.12) openMenu();
    else if (x < w / 3) prev();
    else next();
    return false;
  };

  document.onkeydown = function (e) {
    e = e || window.event;
    var k = e.keyCode;
    if (k === 37 || k === 33) { prev(); return false; }
    if (k === 39 || k === 34 || k === 32) { next(); return false; }
    if (k === 27) { closeMenu(); return false; }
    return true;
  };

  var resizeTimer = null;
  window.onresize = function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      var at = currentParagraph();
      layout();
      show(pageOfParagraph(at));
    }, 200);
  };

  updateSizeControls();
  layout();
  var hash = window.location.hash;
  var m = /^#p=(\d+)$/.exec(hash);
  if (hash === '#fwd') { forwardTurn = true; show(0); }
  else if (hash === '#end') show(pages - 1);
  else if (m) show(pageOfParagraph(parseInt(m[1], 10)));
  else show(pageOfParagraph(num('start')));

  // PW3 native panning ignores DOM touch/scroll controls. Install its scroll
  // surface after initial pagination, with explicit styles as verified on-device.
  var nativePW3 = !('ontouchstart' in window) && /AppleWebKit\/53[1-4]\./.test(navigator.userAgent) &&
    window.screen && screen.width === 1072 && screen.height === 1448 && doc.clientWidth < doc.clientHeight;
  if (nativePW3) {
    var shell = document.createElement('div');
    shell.id = 'reader-shell';
    shell.style.cssText = 'position:relative;width:100%;height:1279px;overflow:scroll';
    var parts = [head, viewport, foot, menu];
    for (var n = 0; n < parts.length; n++) shell.appendChild(parts[n]);
    body.appendChild(shell);
    body.style.cssText = 'position:relative;top:0;left:0;right:auto;bottom:auto;width:104%;height:1260px;overflow:hidden';
    addClass(doc, 'native-pw3');
    setTimeout(function () {
      layout();
      if (hash === '#fwd') show(0);
      else if (hash === '#end') show(pages - 1);
      else if (m) show(pageOfParagraph(parseInt(m[1], 10)));
      else show(pageOfParagraph(num('start')));
    }, 200);
  }

})();
