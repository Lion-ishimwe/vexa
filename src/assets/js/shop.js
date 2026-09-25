/* VEXA shop: search, filters, sorting and paging over the server-rendered product grid */
(function () {
  'use strict';

  const PAGE = 24;

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.querySelector('[data-catalog]');
    if (!root) return;
    const { esc } = window.VEXA;

    const grid = root.querySelector('[data-grid]');
    const cards = Array.from(grid.querySelectorAll('[data-product]')).map((el, i) => ({
      el,
      order: i,
      aisle: el.dataset.aisle,
      brand: el.dataset.brand,
      price: Number(el.dataset.price) || 0,
      title: el.querySelector('.card-title').textContent.trim().toLowerCase(),
      text: el.dataset.text
    }));

    const ui = {
      brands: Array.from(root.querySelectorAll('[data-f-brand]')),
      min: root.querySelector('[data-f-min]'),
      max: root.querySelector('[data-f-max]'),
      priced: root.querySelector('[data-f-priced]'),
      sort: root.querySelector('[data-sort]'),
      aisles: Array.from(root.querySelectorAll('[data-aisle-tab]')),
      count: root.querySelector('[data-result-count]'),
      queryLabel: root.querySelector('[data-query-label]'),
      chips: root.querySelector('[data-chips]'),
      empty: root.querySelector('[data-empty]'),
      more: root.querySelector('[data-more]'),
      moreBtn: root.querySelector('[data-more-btn]'),
      moreLabel: root.querySelector('[data-more-label]'),
      filters: root.querySelector('[data-filters]')
    };

    // ---------- State <-> URL ----------
    const params = new URLSearchParams(window.location.search);
    const state = {
      q: (params.get('q') || '').trim(),
      brands: params.getAll('brand'),
      min: params.get('min') || '',
      max: params.get('max') || '',
      priced: params.get('priced') === '1',
      sort: params.get('sort') || 'featured',
      aisle: params.get('aisle') || '',
      shown: PAGE
    };

    ui.brands.forEach((box) => { box.checked = state.brands.includes(box.value); });
    ui.min.value = state.min;
    ui.max.value = state.max;
    ui.priced.checked = state.priced;
    ui.sort.value = state.sort;
    ui.aisles.forEach((b) => b.classList.toggle('is-on', b.dataset.aisleTab === state.aisle));

    const writeUrl = () => {
      const next = new URLSearchParams();
      if (state.q) next.set('q', state.q);
      state.brands.forEach((b) => next.append('brand', b));
      if (state.min) next.set('min', state.min);
      if (state.max) next.set('max', state.max);
      if (state.priced) next.set('priced', '1');
      if (state.sort !== 'featured') next.set('sort', state.sort);
      if (state.aisle) next.set('aisle', state.aisle);
      const qs = next.toString();
      history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    };

    // ---------- Filtering ----------
    const matches = (card) => {
      if (state.aisle && card.aisle !== state.aisle) return false;
      if (state.brands.length && !state.brands.includes(card.brand)) return false;
      if (state.priced && !card.price) return false;
      const min = Number(state.min) || 0;
      const max = Number(state.max) || 0;
      if (min && (!card.price || card.price < min)) return false;
      if (max && (!card.price || card.price > max)) return false;
      if (state.q) {
        const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
        if (!words.every((w) => card.text.includes(w))) return false;
      }
      return true;
    };

    const sorters = {
      featured: (a, b) => a.order - b.order,
      'price-asc': (a, b) => (a.price || Infinity) - (b.price || Infinity) || a.order - b.order,
      'price-desc': (a, b) => b.price - a.price || a.order - b.order,
      name: (a, b) => a.title.localeCompare(b.title)
    };

    const renderChips = () => {
      const chips = [];
      if (state.q) chips.push({ label: `"${state.q}"`, clear: () => { state.q = ''; } });
      state.brands.forEach((b) => chips.push({ label: b, clear: () => { state.brands = state.brands.filter((x) => x !== b); } }));
      if (state.min) chips.push({ label: `From RWF ${Number(state.min).toLocaleString('en-US')}`, clear: () => { state.min = ''; } });
      if (state.max) chips.push({ label: `Up to RWF ${Number(state.max).toLocaleString('en-US')}`, clear: () => { state.max = ''; } });
      if (state.priced) chips.push({ label: 'With price', clear: () => { state.priced = false; } });
      ui.chips.hidden = !chips.length;
      ui.chips.innerHTML = chips.map((c, i) => `<span class="chip">${esc(c.label)}<button type="button" data-chip="${i}" aria-label="Remove filter ${esc(c.label)}"><svg class="icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6 6 18"/></svg></button></span>`).join('')
        + (chips.length > 1 ? '<button type="button" class="chip clear" data-chip-all>Clear all</button>' : '');
      ui.chips.onclick = (event) => {
        const one = event.target.closest('[data-chip]');
        if (one) { chips[Number(one.dataset.chip)].clear(); syncInputs(); apply(); }
        if (event.target.closest('[data-chip-all]')) reset();
      };
    };

    const syncInputs = () => {
      ui.brands.forEach((box) => { box.checked = state.brands.includes(box.value); });
      ui.min.value = state.min;
      ui.max.value = state.max;
      ui.priced.checked = state.priced;
      const header = document.querySelector('[data-search-input]');
      if (header) header.value = state.q;
    };

    const apply = (keepPage) => {
      if (!keepPage) state.shown = PAGE;
      const hits = cards.filter(matches).sort(sorters[state.sort] || sorters.featured);
      const hitSet = new Set(hits);
      // Reorder in place so sorting survives without re-rendering markup
      hits.forEach((card) => grid.appendChild(card.el));
      cards.filter((c) => !hitSet.has(c)).forEach((card) => grid.appendChild(card.el));
      cards.forEach((card) => { card.el.hidden = true; });
      hits.slice(0, state.shown).forEach((card) => { card.el.hidden = false; });

      ui.count.textContent = hits.length;
      ui.queryLabel.textContent = state.q ? ` for "${state.q}"` : '';
      ui.empty.hidden = hits.length > 0;
      grid.hidden = hits.length === 0;
      const remaining = hits.length - Math.min(state.shown, hits.length);
      ui.more.hidden = remaining <= 0;
      ui.moreLabel.textContent = `Showing ${Math.min(state.shown, hits.length)} of ${hits.length}`;
      renderChips();
      writeUrl();
    };

    const reset = () => {
      state.q = ''; state.brands = []; state.min = ''; state.max = ''; state.priced = false; state.aisle = '';
      ui.aisles.forEach((b) => b.classList.toggle('is-on', b.dataset.aisleTab === ''));
      syncInputs();
      apply();
    };

    // ---------- Inputs ----------
    ui.brands.forEach((box) => box.addEventListener('change', () => {
      state.brands = ui.brands.filter((b) => b.checked).map((b) => b.value);
      apply();
    }));
    let priceTimer;
    [ui.min, ui.max].forEach((input) => input.addEventListener('input', () => {
      clearTimeout(priceTimer);
      priceTimer = setTimeout(() => { state.min = ui.min.value; state.max = ui.max.value; apply(); }, 350);
    }));
    ui.priced.addEventListener('change', () => { state.priced = ui.priced.checked; apply(); });
    ui.sort.addEventListener('change', () => { state.sort = ui.sort.value; apply(); });
    ui.aisles.forEach((btn) => btn.addEventListener('click', () => {
      state.aisle = btn.dataset.aisleTab;
      ui.aisles.forEach((b) => b.classList.toggle('is-on', b === btn));
      apply();
    }));
    ui.moreBtn.addEventListener('click', () => { state.shown += PAGE; apply(true); });
    root.querySelector('[data-f-reset]').addEventListener('click', reset);

    // Header search on shop pages filters in place instead of reloading
    const headerForm = document.querySelector('[data-search] form');
    if (headerForm && !root.dataset.lockCat) {
      headerForm.addEventListener('submit', (event) => {
        event.preventDefault();
        state.q = headerForm.querySelector('[data-search-input]').value.trim();
        const panel = document.querySelector('[data-suggest]');
        if (panel) panel.hidden = true;
        apply();
        root.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    // Mobile filter drawer
    const backdrop = document.querySelector('[data-backdrop]');
    document.querySelector('[data-open-filters]').addEventListener('click', () => {
      ui.filters.classList.add('is-open');
      backdrop.classList.add('is-open');
      document.body.classList.add('is-locked');
    });
    root.querySelector('[data-close-filters]').addEventListener('click', () => window.VEXA.closeDrawer());

    const title = document.querySelector('[data-shop-title]');
    if (title && state.q) title.textContent = `Results for "${state.q}"`;

    apply(true);
  });
})();
