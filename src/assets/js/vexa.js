/* VEXA storefront: cart, drawers, search suggestions */
(function () {
  'use strict';

  const CART_KEY = 'vexa-cart';
  const listeners = new Set();

  const esc = (value) => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

  const money = (amount) => (amount > 0 ? 'RWF ' + Math.round(amount).toLocaleString('en-US') : 'Price on request');

  // ---------- Cart store ----------
  const read = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
      return Array.isArray(parsed) ? parsed.filter((line) => line && line.slug && line.qty > 0) : [];
    } catch (error) {
      return [];
    }
  };
  let lines = read();

  const save = () => {
    try { localStorage.setItem(CART_KEY, JSON.stringify(lines)); } catch (error) { /* private mode: cart lives for this page only */ }
    listeners.forEach((fn) => fn(lines.slice()));
  };

  const clampQty = (qty) => Math.max(1, Math.min(99, parseInt(qty, 10) || 1));

  const cart = {
    lines: () => lines.slice(),
    count: () => lines.reduce((n, line) => n + line.qty, 0),
    subtotal: () => lines.reduce((sum, line) => sum + (line.price > 0 ? line.price * line.qty : 0), 0),
    hasQuote: () => lines.some((line) => !(line.price > 0)),
    add(item, qty) {
      const existing = lines.find((line) => line.slug === item.slug);
      if (existing) {
        existing.qty = clampQty(existing.qty + (qty || 1));
      } else {
        lines.push({
          slug: item.slug, title: item.title, brand: item.brand || '',
          price: Number(item.price) || 0, img: item.img || '', qty: clampQty(qty || 1)
        });
      }
      save();
    },
    setQty(slug, qty) {
      const line = lines.find((l) => l.slug === slug);
      if (!line) return;
      line.qty = clampQty(qty);
      save();
    },
    remove(slug) {
      lines = lines.filter((line) => line.slug !== slug);
      save();
    },
    clear() {
      lines = [];
      save();
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    }
  };

  // Another tab changed the cart
  window.addEventListener('storage', (event) => {
    if (event.key === CART_KEY) {
      lines = read();
      listeners.forEach((fn) => fn(lines.slice()));
    }
  });

  const itemFromNode = (node) => ({
    slug: node.dataset.slug,
    title: node.dataset.title,
    brand: node.dataset.brand,
    price: Number(node.dataset.price) || 0,
    img: node.dataset.img
  });

  // ---------- Toast ----------
  let toastTimer = null;
  const toast = (text) => {
    const el = document.querySelector('[data-toast]');
    if (!el) return;
    el.querySelector('[data-toast-text]').textContent = text;
    el.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('is-on'), 2400);
  };

  // ---------- Drawers ----------
  const backdrop = () => document.querySelector('[data-backdrop]');
  let openDrawerEl = null;
  let lastFocus = null;

  const openDrawer = (id) => {
    const drawer = document.getElementById(id);
    if (!drawer) return;
    closeDrawer();
    lastFocus = document.activeElement;
    openDrawerEl = drawer;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    backdrop().classList.add('is-open');
    document.body.classList.add('is-locked');
    const focusable = drawer.querySelector('button, a');
    if (focusable) focusable.focus();
  };

  const closeDrawer = () => {
    document.querySelectorAll('.drawer.is-open, .filters.is-open').forEach((el) => {
      el.classList.remove('is-open');
      el.setAttribute('aria-hidden', 'true');
    });
    const bd = backdrop();
    if (bd) bd.classList.remove('is-open');
    document.body.classList.remove('is-locked');
    if (openDrawerEl && lastFocus) lastFocus.focus();
    openDrawerEl = null;
  };

  // ---------- Rendering ----------
  const qtyControl = (line) => `
    <div class="qty" data-line-qty="${esc(line.slug)}">
      <button type="button" data-line-step="-1" aria-label="Decrease quantity">&minus;</button>
      <input type="number" min="1" max="99" value="${line.qty}" aria-label="Quantity for ${esc(line.title)}" data-line-input>
      <button type="button" data-line-step="1" aria-label="Increase quantity">+</button>
    </div>`;

  const renderHeader = () => {
    const count = cart.count();
    document.querySelectorAll('[data-cart-count]').forEach((el) => {
      el.textContent = count > 99 ? '99+' : String(count);
      el.dataset.empty = count === 0 ? 'true' : 'false';
    });
    document.querySelectorAll('[data-cart-total-short]').forEach((el) => {
      el.textContent = 'RWF ' + cart.subtotal().toLocaleString('en-US');
    });
    document.querySelectorAll('[data-cart-subtotal]').forEach((el) => {
      el.textContent = 'RWF ' + cart.subtotal().toLocaleString('en-US');
    });
    document.querySelectorAll('[data-cart-items-label]').forEach((el) => {
      el.textContent = count ? `(${count} item${count === 1 ? '' : 's'})` : '';
    });
    document.querySelectorAll('[data-quote-note]').forEach((el) => { el.hidden = !cart.hasQuote(); });
    document.querySelectorAll('[data-add-to-cart]').forEach((btn) => {
      btn.classList.toggle('is-added', lines.some((line) => line.slug === btn.dataset.slug));
    });
  };

  const renderMini = () => {
    const body = document.querySelector('[data-mini-lines]');
    const foot = document.querySelector('[data-mini-foot]');
    if (!body) return;
    if (!lines.length) {
      body.innerHTML = `<div class="mini-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M5 8h14l-1 12H6z"/><path d="M9 8V6.5a3 3 0 0 1 6 0V8"/></svg>
        <p><b>Your cart is empty.</b></p><p style="margin:6px 0 18px">Find something you like in the store.</p>
        <a class="btn btn-gold" href="/shop/">Start shopping</a></div>`;
      if (foot) foot.hidden = true;
      return;
    }
    if (foot) foot.hidden = false;
    body.innerHTML = lines.map((line) => `
      <div class="mini-line">
        <a href="/product/${esc(line.slug)}/"><img src="${esc(line.img)}" alt="" referrerpolicy="no-referrer"></a>
        <div>
          <a class="t" href="/product/${esc(line.slug)}/">${esc(line.title)}</a>
          <p class="m">${esc(line.brand || '')}${line.brand ? ' · ' : ''}${esc(money(line.price))}</p>
          <div style="display:flex;align-items:center">${qtyControl(line)}<button type="button" class="remove" data-line-remove="${esc(line.slug)}">Remove</button></div>
        </div>
        <span class="p">${line.price > 0 ? esc(money(line.price * line.qty)) : 'On request'}</span>
      </div>`).join('');
  };

  const render = () => { renderHeader(); renderMini(); };
  cart.subscribe(render);

  // ---------- Events ----------
  document.addEventListener('click', (event) => {
    const add = event.target.closest('[data-add-to-cart]');
    if (add) {
      event.preventDefault();
      cart.add(itemFromNode(add), 1);
      toast(`Added to cart: ${add.dataset.title}`);
      return;
    }
    const opener = event.target.closest('[data-open-drawer]');
    if (opener) {
      event.preventDefault();
      openDrawer(opener.dataset.openDrawer);
      return;
    }
    if (event.target.closest('[data-close-drawer]') || event.target.matches('[data-backdrop]')) {
      closeDrawer();
      return;
    }
    const step = event.target.closest('[data-line-step]');
    if (step) {
      const wrap = step.closest('[data-line-qty]');
      const line = lines.find((l) => l.slug === wrap.dataset.lineQty);
      if (!line) return;
      const next = line.qty + Number(step.dataset.lineStep);
      if (next < 1) cart.remove(line.slug); else cart.setQty(line.slug, next);
      return;
    }
    const remove = event.target.closest('[data-line-remove]');
    if (remove) {
      cart.remove(remove.dataset.lineRemove);
    }
  });

  document.addEventListener('change', (event) => {
    if (event.target.matches('[data-line-input]')) {
      cart.setQty(event.target.closest('[data-line-qty]').dataset.lineQty, event.target.value);
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeDrawer();
  });

  // ---------- Search suggestions ----------
  const setupSearch = () => {
    const box = document.querySelector('[data-search]');
    if (!box) return;
    const input = box.querySelector('[data-search-input]');
    const panel = box.querySelector('[data-suggest]');
    let index = null;
    let active = -1;

    const params = new URLSearchParams(window.location.search);
    if (params.get('q') && window.location.pathname.startsWith('/shop')) input.value = params.get('q');

    const load = () => {
      if (!index) {
        index = fetch('/search-index.json').then((r) => (r.ok ? r.json() : [])).catch(() => []);
      }
      return index;
    };

    const hide = () => { panel.hidden = true; active = -1; };

    const show = (items, term) => {
      if (!items.length) {
        panel.innerHTML = `<p class="s-empty">No products match "${esc(term)}". Press Enter to search the whole store.</p>`;
      } else {
        panel.innerHTML = items.map((p) => `
          <a href="/product/${esc(p.s)}/">
            <img src="${esc(p.i)}" alt="" referrerpolicy="no-referrer">
            <span><span class="s-title">${esc(p.t)}</span><br><span class="s-meta">${esc([p.b, p.a].filter(Boolean).join(' · '))}</span></span>
            <span class="s-price">${esc(money(p.p))}</span>
          </a>`).join('') + `<a class="s-all" href="/shop/?q=${encodeURIComponent(term)}">See all results for "${esc(term)}"</a>`;
      }
      panel.hidden = false;
      active = -1;
    };

    input.addEventListener('focus', load);
    input.addEventListener('input', () => {
      const term = input.value.trim();
      if (term.length < 2) { hide(); return; }
      load().then((all) => {
        if (input.value.trim() !== term) return;
        const words = term.toLowerCase().split(/\s+/);
        const hits = all.filter((p) => {
          const hay = `${p.t} ${p.b} ${p.a} ${p.k}`.toLowerCase();
          return words.every((w) => hay.includes(w));
        }).slice(0, 6);
        show(hits, term);
      });
    });

    input.addEventListener('keydown', (event) => {
      const links = Array.from(panel.querySelectorAll('a'));
      if (panel.hidden || !links.length) return;
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        active = (active + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
        links.forEach((a, i) => a.classList.toggle('is-active', i === active));
      } else if (event.key === 'Enter' && active >= 0) {
        event.preventDefault();
        links[active].click();
      } else if (event.key === 'Escape') {
        hide();
      }
    });

    document.addEventListener('click', (event) => {
      if (!box.contains(event.target)) hide();
    });
  };

  // Linked manufacturer photos can move or disappear; show the VEXA placeholder instead of a broken image
  const PLACEHOLDER = '/assets/img/placeholder.svg';
  const useFallback = (img) => {
    if (img.dataset.fellBack) return;
    img.dataset.fellBack = '1';
    img.src = img.dataset.fallback || PLACEHOLDER;
    const box = img.closest('.card-media, .pdp-media');
    if (box) box.classList.add('is-placeholder');
  };
  document.addEventListener('error', (event) => {
    if (event.target.tagName === 'IMG') useFallback(event.target);
  }, true);
  const sweepBroken = () => document.querySelectorAll('img').forEach((img) => {
    if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) useFallback(img);
  });

  window.VEXA = Object.assign(window.VEXA || {}, { cart, money, esc, toast, openDrawer, closeDrawer, itemFromNode });

  // Hero video: respect reduced motion, and don't play while scrolled out of view
  const setupHeroVideo = () => {
    const video = document.querySelector('[data-hero-video]');
    if (!video) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)');
    const play = () => { const p = video.play(); if (p) p.catch(() => {}); };
    if (still.matches) {
      video.removeAttribute('autoplay');
      video.pause();
      return;
    }
    if ('IntersectionObserver' in window) {
      new IntersectionObserver((entries) => {
        entries.forEach((entry) => (entry.isIntersecting ? play() : video.pause()));
      }, { threshold: 0.15 }).observe(video);
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    render();
    setupSearch();
    sweepBroken();
    setupHeroVideo();
  });
})();
