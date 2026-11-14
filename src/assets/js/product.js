/* VEXA product page: quantity, add to cart, buy now, tabs */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    const buy = document.querySelector('[data-buy]');
    if (buy) {
      const input = buy.querySelector('[data-qty-input]');
      const qty = () => Math.max(1, Math.min(99, parseInt(input.value, 10) || 1));

      buy.querySelectorAll('[data-step]').forEach((btn) => btn.addEventListener('click', () => {
        input.value = Math.max(1, Math.min(99, qty() + Number(btn.dataset.step)));
      }));
      input.addEventListener('change', () => { input.value = qty(); });

      buy.querySelector('[data-buy-add]').addEventListener('click', () => {
        window.VEXA.cart.add(window.VEXA.itemFromNode(buy), qty());
        window.VEXA.openDrawer('mini-cart');
      });
      buy.querySelector('[data-buy-now]').addEventListener('click', () => {
        const item = window.VEXA.itemFromNode(buy);
        if (!window.VEXA.cart.lines().some((line) => line.slug === item.slug)) {
          window.VEXA.cart.add(item, qty());
        }
        window.location.href = '/checkout/';
      });
    }

    // Photo gallery: thumbnails swap the main photo
    const gallery = document.querySelector('[data-gallery]');
    if (gallery) {
      const main = gallery.querySelector('[data-gallery-main]');
      const spin = gallery.querySelector('[data-spin]');
      const thumbs = Array.from(gallery.querySelectorAll('.thumb'));
      const select = (btn) => thumbs.forEach((t) => t.classList.toggle('is-on', t === btn));
      thumbs.forEach((btn) => btn.addEventListener('click', () => {
        select(btn);
        if (btn.hasAttribute('data-spin-open')) { openSpin(); return; }
        if (spin) spin.hidden = true;
        main.hidden = false;
        delete main.dataset.fellBack; delete main.dataset.triedOriginal;
        main.dataset.original = btn.dataset.original;
        main.src = btn.dataset.thumb;
      }));

      // 360 view: drag (or swipe) across the photo to turn the product
      let frames = [];
      let index = 0;
      const openSpin = () => {
        if (!spin) return;
        const img = spin.querySelector('img');
        if (!frames.length) {
          frames = JSON.parse(spin.dataset.spin);
          frames.forEach((src) => { const pre = new Image(); pre.referrerPolicy = 'no-referrer'; pre.src = src; });
        }
        main.hidden = true;
        spin.hidden = false;
        img.src = frames[index];
        if (window.VEXA && window.VEXA.track) window.VEXA.track('view-360', { product: document.querySelector('[data-buy]')?.dataset.title });
      };
      if (spin) {
        const img = spin.querySelector('img');
        let startX = null;
        let startIndex = 0;
        const step = (n) => { index = (n % frames.length + frames.length) % frames.length; img.src = frames[index]; };
        spin.addEventListener('pointerdown', (e) => { startX = e.clientX; startIndex = index; spin.setPointerCapture(e.pointerId); spin.classList.add('is-turning'); });
        spin.addEventListener('pointermove', (e) => { if (startX !== null) step(startIndex + Math.round((startX - e.clientX) / 10)); });
        const end = () => { startX = null; spin.classList.remove('is-turning'); };
        spin.addEventListener('pointerup', end);
        spin.addEventListener('pointercancel', end);
      }
    }

    const tabs = document.querySelector('[data-tabs]');
    if (tabs) {
      const buttons = Array.from(tabs.querySelectorAll('[role="tab"]'));
      buttons.forEach((btn) => btn.addEventListener('click', () => {
        buttons.forEach((b) => {
          const on = b === btn;
          b.setAttribute('aria-selected', on ? 'true' : 'false');
          document.getElementById(b.getAttribute('aria-controls')).hidden = !on;
        });
      }));
    }
  });
})();
