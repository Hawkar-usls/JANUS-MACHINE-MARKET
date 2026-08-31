(() => {
  'use strict';

  let pricing = null;
  let readiness = null;
  let frozenPreview = null;

  const q = sel => document.querySelector(sel);

  function money(micros) {
    const n = Math.max(0, Number(micros || 0)) / 1_000_000;
    return `${n.toLocaleString('en-US', {minimumFractionDigits: n < 1 ? 2 : 2, maximumFractionDigits: 6})} USDT`;
  }

  function discountBps(qty) {
    const tiers = [...(pricing?.quantity_discounts || [])].sort((a,b) => Number(a.min_quantity) - Number(b.min_quantity));
    let discount = 0;
    for (const tier of tiers) if (Number(qty) >= Number(tier.min_quantity)) discount = Number(tier.discount_bps || 0);
    return discount;
  }

  function itemPrice(item) {
    const p = pricing?.products?.[item.sku];
    if (!p || p.local_price === null || !Number.isFinite(Number(p.base_unit_usdt_micros))) return {priced:false, reason:p?.authority || p?.status || 'PRICE_NOT_PUBLISHED'};
    const mode = p.modes?.[item.mode];
    if (!mode) return {priced:false, reason:'MODE_NOT_PRICED'};
    const qty = Math.max(1, Number(item.qty || 1));
    const base = Number(p.base_unit_usdt_micros);
    const multiplier = Number(mode.multiplier_bps || 10000);
    const unit = Math.round(base * multiplier / 10000);
    const gross = unit * qty;
    const discount = discountBps(qty);
    const net = Math.round(gross * (10000 - discount) / 10000);
    return {priced:true, qty, unit_micros:unit, gross_micros:gross, discount_bps:discount, discount_micros:gross-net, subtotal_micros:net, billing_unit:p.billing_unit || item.unit || 'unit'};
  }

  function basketPrice() {
    const lines = (state.loadout || []).map(item => ({item, price:itemPrice(item)}));
    const priced = lines.filter(x => x.price.priced);
    const unpriced = lines.filter(x => !x.price.priced);
    return {
      lines,
      priced,
      unpriced,
      gross_micros: priced.reduce((a,x) => a + x.price.gross_micros, 0),
      discount_micros: priced.reduce((a,x) => a + x.price.discount_micros, 0),
      total_micros: priced.reduce((a,x) => a + x.price.subtotal_micros, 0)
    };
  }

  function currentGateLabel() {
    if (readiness?.money_enabled === true && readiness?.autonomous_purchase_declared === true) return 'PAYMENT ROUTE READY';
    return 'PAYMENT GATE LOCKED';
  }

  function refreshCatalogPrices() {
    if (!pricing) return;
    document.querySelectorAll('.sku-card').forEach(card => {
      const sku = card.querySelector('h3')?.textContent?.trim();
      if (!sku) return;
      const input = card.querySelector('.sku-actions input');
      const select = card.querySelector('.sku-actions select');
      const actions = card.querySelector('.sku-actions');
      if (!actions) return;
      let line = card.querySelector('.sku-price-line');
      if (!line) {
        line = document.createElement('div');
        line.className = 'sku-price-line';
        actions.insertAdjacentElement('beforebegin', line);
      }
      const update = () => {
        const qty = Math.max(1, Number(input?.value || 1));
        const mode = String(select?.value || 'STANDARD');
        const result = itemPrice({sku, qty, mode});
        if (!result.priced) {
          line.innerHTML = `<span>PRICE</span><b>${result.reason === 'DELEGATED_TO_JANUS_HELIOS' ? 'DELEGATED' : 'NOT PUBLISHED'}</b>`;
          return;
        }
        const discount = result.discount_bps ? `<small> · volume −${(result.discount_bps/100).toFixed(0)}%</small>` : '';
        line.innerHTML = `<span>${money(result.unit_micros)} / ${result.billing_unit}</span><b>${money(result.subtotal_micros)}${discount}</b>`;
      };
      input?.addEventListener('input', update);
      select?.addEventListener('change', update);
      update();
    });
  }

  function refreshLoadoutPrices() {
    if (!pricing) return;
    const calc = basketPrice();
    const rows = document.querySelectorAll('#loadoutList .load-item');
    rows.forEach((row, i) => {
      const entry = calc.lines[i];
      if (!entry) return;
      let meta = row.querySelector('.load-price');
      if (!meta) {
        meta = document.createElement('div');
        meta.className = 'load-price';
        row.querySelector('div')?.append(meta);
      }
      if (!entry.price.priced) meta.textContent = 'price not published';
      else {
        const d = entry.price.discount_bps ? ` · −${entry.price.discount_bps/100}% volume` : '';
        meta.textContent = `${money(entry.price.unit_micros)} each · subtotal ${money(entry.price.subtotal_micros)}${d}`;
      }
    });

    const host = q('.quote-lines');
    if (!host) return;
    const unpriced = calc.unpriced.length;
    host.innerHTML = `
      <div><span>Ratecard</span><b>${pricing.status === 'PREVIEW_RATECARD_NOT_LIVE' ? 'PREVIEW' : pricing.status}</b></div>
      <div><span>Gross</span><b>${money(calc.gross_micros)}</b></div>
      <div><span>Volume savings</span><b>${calc.discount_micros ? '−' + money(calc.discount_micros) : money(0)}</b></div>
      <div class="quote-total"><span>Estimated total</span><b>${money(calc.total_micros)}</b></div>
      ${unpriced ? `<div><span>Unpriced items</span><b class="amber">${unpriced}</b></div>` : ''}
      <div><span>Quote validity</span><b>${Math.round(Number(pricing.quote_ttl_seconds || 900)/60)} MIN</b></div>
      <div><span>Payments</span><b class="amber">${currentGateLabel()}</b></div>`;
  }

  function snapshotLoadout() {
    const calc = basketPrice();
    return {
      schema:'janus.machine_market.browser_quote_preview.v1',
      pricing_version:pricing?.version || null,
      currency:pricing?.currency || 'USDT',
      network:pricing?.network || 'ethereum-mainnet',
      chain_id:pricing?.chain_id || 1,
      items:calc.lines.map(x => ({sku:x.item.sku, mode:x.item.mode, quantity:x.item.qty, priced:x.price.priced, subtotal_usdt_micros:x.price.priced ? x.price.subtotal_micros : null})),
      total_usdt_micros:calc.total_micros,
      unpriced_skus:calc.unpriced.map(x => x.item.sku)
    };
  }

  async function sha256(value) {
    const bytes = new TextEncoder().encode(JSON.stringify(value));
    const hash = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(hash)].map(b => b.toString(16).padStart(2,'0')).join('');
  }

  function refreshTradePricing() {
    if (!pricing || !q('#tradeModal')?.classList.contains('open')) return;
    const calc = basketPrice();
    const tradeItems = q('#buyerTradeItems');
    if (tradeItems) {
      tradeItems.innerHTML = calc.lines.map(({item,price}) => `<div class="trade-item"><span>${item.sku}<small>${item.mode} · ${item.qty} × ${price.priced ? money(price.unit_micros) : 'unpriced'}</small></span><b>${price.priced ? money(price.subtotal_micros) : 'QUOTE'}</b></div>`).join('');
    }

    let box = q('#pricingQuotePreview');
    if (!box) {
      box = document.createElement('section');
      box.id = 'pricingQuotePreview';
      box.className = 'pricing-quote-preview';
      q('.trade-cols')?.insertAdjacentElement('afterend', box);
    }
    const ttl = Number(pricing.quote_ttl_seconds || 900);
    const expires = new Date(Date.now() + ttl*1000);
    frozenPreview = {snapshot:snapshotLoadout(), created_at:new Date().toISOString(), expires_at:expires.toISOString(), preview_id:`preview-${Date.now()}`};
    box.innerHTML = `
      <div class="pricing-quote-head"><span>FROZEN QUOTE PREVIEW</span><b>${pricing.version}</b></div>
      <div class="pricing-quote-total"><span>TOTAL</span><strong>${money(calc.total_micros)}</strong></div>
      <div class="pricing-quote-grid">
        <span>Asset <b>${pricing.currency}</b></span>
        <span>Network <b>Ethereum Mainnet</b></span>
        <span>Expires <b>${expires.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</b></span>
        <span>Receiver <b>${String(pricing.declared_receiving_address || '').slice(0,8)}…${String(pricing.declared_receiving_address || '').slice(-6)}</b></span>
      </div>
      <div class="pricing-gate ${readiness?.money_enabled ? 'ready' : 'locked'}">${currentGateLabel()} · browser preview is not a payable invoice</div>`;
    sha256(frozenPreview.snapshot).then(hash => {
      frozenPreview.preview_hash = hash;
      const head = q('#pricingQuotePreview .pricing-quote-head b');
      if (head) head.textContent = `${pricing.version} · ${hash.slice(0,12)}`;
    }).catch(()=>{});
  }

  function appendPricingSurface() {
    const grid = q('#surfaceGrid');
    if (!grid || grid.querySelector('a[href="PRICING.json"]')) return;
    const a = document.createElement('a');
    a.className = 'surface'; a.href = 'PRICING.json';
    a.innerHTML = '<b>PRICING.json</b><small>Public deterministic preview ratecard</small>';
    grid.prepend(a);
  }

  function patch() {
    if (typeof renderCatalog === 'function' && !renderCatalog.__pricingPatched) {
      const base = renderCatalog;
      renderCatalog = function(){ base(); refreshCatalogPrices(); };
      renderCatalog.__pricingPatched = true;
    }
    if (typeof renderLoadout === 'function' && !renderLoadout.__pricingPatched) {
      const base = renderLoadout;
      renderLoadout = function(){ base(); refreshLoadoutPrices(); };
      renderLoadout.__pricingPatched = true;
    }
    if (typeof openTrade === 'function' && !openTrade.__pricingPatched) {
      const base = openTrade;
      openTrade = function(){ base(); refreshTradePricing(); };
      openTrade.__pricingPatched = true;
      const review = q('#reviewTrade');
      if (review) review.onclick = openTrade;
    }
  }

  async function init() {
    try {
      [pricing, readiness] = await Promise.all([
        fetch('PRICING.json', {cache:'no-store'}).then(r => r.json()),
        fetch('COMMERCE_READINESS.json', {cache:'no-store'}).then(r => r.json())
      ]);
      window.JANUS_PRICING = pricing;
      window.JANUS_COMMERCE_READINESS = readiness;
      patch();
      if (typeof renderCatalog === 'function') renderCatalog();
      if (typeof renderLoadout === 'function') renderLoadout();
      appendPricingSurface();
    } catch (err) {
      console.error('JANUS pricing layer failed closed', err);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
