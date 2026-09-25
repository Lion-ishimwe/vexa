/* VEXA cart page and checkout */
(function () {
  'use strict';

  const ORDER_KEY = 'vexa-last-order';

  document.addEventListener('DOMContentLoaded', () => {
    const { cart, esc, money } = window.VEXA;

    const qtyControl = (line) => `
      <div class="qty" data-line-qty="${esc(line.slug)}">
        <button type="button" data-line-step="-1" aria-label="Decrease quantity">&minus;</button>
        <input type="number" min="1" max="99" value="${line.qty}" aria-label="Quantity for ${esc(line.title)}" data-line-input>
        <button type="button" data-line-step="1" aria-label="Increase quantity">+</button>
      </div>`;

    // ---------- Cart page ----------
    const cartPage = document.querySelector('[data-cart-page]');
    if (cartPage) {
      const full = cartPage.querySelector('[data-cart-full]');
      const empty = cartPage.querySelector('[data-cart-empty]');
      const list = cartPage.querySelector('[data-cart-lines]');
      const qtyLabel = cartPage.querySelector('[data-cart-qty]');

      const render = () => {
        const lines = cart.lines();
        full.hidden = !lines.length;
        empty.hidden = lines.length > 0;
        qtyLabel.textContent = cart.count();
        list.innerHTML = lines.map((line) => `
          <div class="cart-line">
            <a href="/product/${esc(line.slug)}/"><img src="${esc(line.img)}" alt="" referrerpolicy="no-referrer"></a>
            <div>
              <a class="t" href="/product/${esc(line.slug)}/">${esc(line.title)}</a>
              <p class="m">${esc(line.brand ? line.brand + ' · ' : '')}${esc(money(line.price))} each</p>
              <div style="display:flex;align-items:center">${qtyControl(line)}<button type="button" class="remove" data-line-remove="${esc(line.slug)}">Remove</button></div>
            </div>
            <div class="lt">
              <b>${line.price > 0 ? esc(money(line.price * line.qty)) : 'On request'}</b>
              ${line.qty > 1 && line.price > 0 ? `<small>${line.qty} × ${esc(money(line.price))}</small>` : ''}
            </div>
          </div>`).join('');
      };
      cart.subscribe(render);
      render();
    }

    // ---------- Checkout ----------
    const page = document.querySelector('[data-checkout-page]');
    if (!page) return;
    const form = page.querySelector('[data-checkout-form]');
    const empty = page.querySelector('[data-cart-empty]');
    const confirm = page.querySelector('[data-confirm]');
    const summary = page.querySelector('[data-os-lines]');
    const address = form.querySelector('[data-address]');

    const showConfirm = (order) => {
      form.hidden = true;
      empty.hidden = true;
      confirm.hidden = false;
      document.querySelectorAll('[data-steps] span').forEach((step, i, all) => step.classList.toggle('on', i === all.length - 1));
      confirm.querySelector('[data-confirm-name]').textContent = order.firstName;
      confirm.querySelector('[data-confirm-ref]').textContent = 'Order ' + order.ref;
      confirm.querySelector('[data-confirm-wa]').href = `https://wa.me/${window.VEXA.whatsapp}?text=${encodeURIComponent(order.message)}`;
      window.scrollTo({ top: 0 });
    };

    const renderSummary = () => {
      const lines = cart.lines();
      if (!confirm.hidden) return;
      form.hidden = !lines.length;
      empty.hidden = lines.length > 0;
      summary.innerHTML = lines.map((line) => `
        <div class="os-line">
          <div class="im"><img src="${esc(line.img)}" alt="" referrerpolicy="no-referrer"><span class="q">${line.qty}</span></div>
          <span class="t">${esc(line.title)}</span>
          <span class="p">${line.price > 0 ? esc(money(line.price * line.qty)) : 'On request'}</span>
        </div>`).join('');
    };

    // Returning to a just-placed order (e.g. after WhatsApp) shows its confirmation again
    try {
      const last = JSON.parse(localStorage.getItem(ORDER_KEY) || 'null');
      if (last && window.location.hash === '#order-' + last.ref) {
        showConfirm(last);
      }
    } catch (error) { /* ignore */ }

    cart.subscribe(renderSummary);
    renderSummary();

    const toggleAddress = () => {
      const pickup = form.elements.delivery.value === 'Pick up';
      address.hidden = pickup;
      address.querySelectorAll('[required], [data-was-required]').forEach((input) => {
        if (pickup) { input.removeAttribute('required'); input.dataset.wasRequired = '1'; } else { input.setAttribute('required', ''); }
      });
    };
    form.querySelectorAll('input[name="delivery"]').forEach((r) => r.addEventListener('change', toggleAddress));

    form.querySelectorAll('.input').forEach((input) => input.addEventListener('input', () => {
      input.closest('.field').classList.remove('has-error');
    }));

    const validate = () => {
      let first = null;
      form.querySelectorAll('[required]').forEach((input) => {
        let bad = !input.value.trim();
        if (input.type === 'tel' && !bad) bad = input.value.replace(/\D/g, '').length < 9;
        input.closest('.field').classList.toggle('has-error', bad);
        if (bad && !first) first = input;
      });
      if (first) first.focus();
      return !first;
    };

    const makeRef = () => {
      const d = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      return `VX${String(d.getFullYear()).slice(2)}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${Math.floor(1000 + Math.random() * 9000)}`;
    };

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!cart.lines().length || !validate()) return;

      const f = new FormData(form);
      const val = (k) => String(f.get(k) || '').trim();
      const ref = makeRef();
      const lines = cart.lines();
      const msg = [
        `New ${window.VEXA.name} order: ${ref}`,
        '',
        ...lines.map((l, i) => `${i + 1}. ${l.title} × ${l.qty}: ${l.price > 0 ? money(l.price * l.qty) : 'price on request'}`),
        '',
        `Subtotal: ${money(cart.subtotal())}${cart.hasQuote() ? ' (+ items on request)' : ''}`,
        '',
        `Name: ${val('name')}`,
        `Phone: ${val('phone')}`
      ];
      if (val('email')) msg.push(`Email: ${val('email')}`);
      msg.push(`Delivery: ${val('delivery')}`);
      if (val('delivery') !== 'Pick up') {
        msg.push(`Address: ${[val('address'), val('area'), val('district')].filter(Boolean).join(', ')}`);
      }
      msg.push(`Installation: ${f.get('installation') ? 'Yes, please quote installation' : 'No'}`);
      msg.push(`Payment: ${val('payment')}`);
      if (val('notes')) msg.push(`Notes: ${val('notes')}`);

      const order = { ref, firstName: val('name').split(/\s+/)[0], message: msg.join('\n') };
      try { localStorage.setItem(ORDER_KEY, JSON.stringify(order)); } catch (error) { /* ignore */ }
      history.replaceState(null, '', '#order-' + ref);
      showConfirm(order);
      cart.clear();
    });
  });
})();
