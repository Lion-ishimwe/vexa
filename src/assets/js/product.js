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
