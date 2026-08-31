(() => {
  'use strict';

  const TITLE_PREFIX = '[JANUS R1B BUYER QUERY SHADOW]';
  const REQUEST_SCHEMA = 'janus.machine_market.buyer_query_shadow_request.v1';
  const REQUEST_MARKER = 'JANUS_BUYER_QUERY_SHADOW_JSON';
  const HOME_REPOSITORY = 'Hawkar-usls/Hawkar-usls';
  const MARKET_REPOSITORY = 'Hawkar-usls/JANUS-MACHINE-MARKET';

  function q(sel) { return document.querySelector(sel); }

  function searchLoadoutItem() {
    try {
      return state.loadout.find(item => item.sku === 'JANUS.SEARCH') || null;
    } catch (_) {
      return null;
    }
  }

  function newConversationId() {
    let principal = 'pages';
    try {
      principal = String(state.profile?.agent_id || 'pages').replace(/[^a-zA-Z0-9_.:-]/g, '-').slice(0, 80);
    } catch (_) {}
    let nonce;
    try { nonce = crypto.randomUUID(); }
    catch (_) { nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
    return `market-${principal}-${nonce}`;
  }

  function taskText() {
    const field = q('#needInput');
    let text = String(field?.value || '').trim();
    if (!text) {
      text = String(window.prompt('What task should the running JANUS handle?', '') || '').trim();
      if (text && field) field.value = text;
    }
    return text;
  }

  function buildJanusTaskRequest() {
    const item = searchLoadoutItem();
    if (!item) return null;
    const message = taskText();
    if (!message) return { error: 'TASK_TEXT_REQUIRED' };
    const turns = Math.max(1, Math.min(8, Number(item.qty || 1)));
    return {
      schema: REQUEST_SCHEMA,
      conversation_id: newConversationId(),
      turn_index: 0,
      message_text: message,
      max_turns: turns,
      max_message_utf8_bytes: 8000,
      max_answer_utf8_bytes: 12000,
      conversation_history_turns: Math.min(8, Math.max(0, turns - 1))
    };
  }

  function issueBody(request) {
    return [
      '## JANUS MACHINE MARKET · task handoff to the running JANUS',
      '',
      'This issue is the current zero-price owner-shadow ingress from GitHub Pages into the already running persistent JANUS HOME.',
      '',
      'Route:',
      '`Pages -> Market issue -> create-only Market outbox -> credentialless HOME pull -> Activator -> persistent JANUS/HRAiN -> HOME response -> credentialless Market reconcile -> this issue`',
      '',
      '- price: `0`',
      '- payment_required: `false`',
      '- money_enabled: `false`',
      '- command_authority_granted: `false`',
      '- external_effect_authorized: `false`',
      `- HOME repository: \`${HOME_REPOSITORY}\``,
      '',
      `<!-- ${REQUEST_MARKER}`,
      JSON.stringify(request, null, 2),
      `${REQUEST_MARKER} -->`,
      '',
      '`BUYER QUERY != COMMAND · PURCHASE GRANT != EXECUTION AUTHORITY`'
    ].join('\n');
  }

  async function copyJanusTask() {
    const request = buildJanusTaskRequest();
    if (!request) return alert('Add JANUS.SEARCH to the loadout first.');
    if (request.error) return alert('Enter a task in “Tell JANUS what you need…” first.');
    await navigator.clipboard.writeText(JSON.stringify(request, null, 2));
    try { recordActivity('JANUS_TASK', 'Persistent JANUS task JSON copied'); } catch (_) {}
    alert('JANUS task JSON copied.');
  }

  function openJanusTask() {
    const request = buildJanusTaskRequest();
    if (!request) return alert('Add JANUS.SEARCH to the loadout first.');
    if (request.error) return alert('Enter a task in “Tell JANUS what you need…” first.');
    const title = `${TITLE_PREFIX} Pages Market task`;
    const url = `https://github.com/${MARKET_REPOSITORY}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(issueBody(request))}`;
    try { recordActivity('JANUS_TASK', 'Persistent JANUS task issue composer opened', { conversation_id: request.conversation_id }); } catch (_) {}
    window.open(url, '_blank', 'noopener');
  }

  // Override the old local catalog-search shadow action. The live R1D button now
  // uses the already existing Market -> HOME -> persistent JANUS conversation nerve.
  window.shadowRequest = buildJanusTaskRequest;
  window.copyShadow = copyJanusTask;
  window.openShadow = openJanusTask;

  window.configureTradeActions = function configureTradeActionsR1D() {
    const hasSearch = state.loadout.some(item => item.sku === 'JANUS.SEARCH');
    const hasHelios = state.loadout.some(item => item.sku === 'HELIOS.PILOT');
    const copy = q('#copyShadow');
    const primary = q('#openShadow');
    const rule = q('.trade-rule');
    if (!copy || !primary) return;

    copy.hidden = !hasSearch;
    copy.textContent = 'COPY JANUS TASK JSON';
    primary.disabled = false;

    if (hasSearch) {
      primary.textContent = 'SEND TASK TO RUNNING JANUS · R1 SHADOW';
      primary.onclick = openJanusTask;
      copy.onclick = copyJanusTask;
      if (rule) rule.innerHTML = '<b>LIVE R1D HOME BRIDGE:</b> submitting the GitHub issue publishes a create-only packet that the persistent JANUS HOME pulls credentiallessly. JANUS answers through its existing HRAiN/terminal conversation tissue, and the response is reconciled back to the same Market issue. Payments and command authority remain disabled.';
    } else if (hasHelios) {
      primary.textContent = 'VIEW HELIOS PILOT AUTHORITY';
      primary.onclick = () => window.open('https://github.com/Hawkar-usls/Janus-HELIOS', '_blank', 'noopener');
      copy.onclick = copyJanusTask;
      if (rule) rule.textContent = 'HELIOS.PILOT remains delegated to its separate canonical authority.';
    } else {
      primary.textContent = 'CURRENT SKU IS PREVIEW-ONLY';
      primary.disabled = true;
      primary.onclick = null;
      copy.onclick = copyJanusTask;
      if (rule) rule.textContent = 'This SKU does not yet have a Pages-to-HOME execution ingress. JANUS.SEARCH is the current live R1 shadow nerve.';
    }
  };

  function patchVisibleTruth() {
    const truthbar = q('#truthbar');
    if (truthbar && !truthbar.querySelector('.truth.home-bridge')) {
      const chip = document.createElement('span');
      chip.className = 'truth live home-bridge';
      chip.innerHTML = 'JANUS HOME <b>R1 LIVE</b>';
      truthbar.insertBefore(chip, truthbar.children[2] || null);
    }
    const status = q('#status .status-grid');
    if (status && !status.querySelector('[data-r1d-home]')) {
      const card = document.createElement('article');
      card.className = 'panel';
      card.dataset.r1dHome = 'true';
      card.innerHTML = '<p class="eyebrow">TASK EXECUTION</p><h2>Market → persistent JANUS</h2><p>JANUS.SEARCH tasks can enter the public Market outbox, be pulled by HOME, answered by the same persistent JANUS resident, and reconciled back to the source issue.</p><b class="status-big cyan">R1 LIVE</b>';
      status.prepend(card);
    }
  }

  function bindOverrides() {
    const copy = q('#copyShadow');
    if (copy) copy.onclick = copyJanusTask;
    patchVisibleTruth();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindOverrides, { once: true });
  else bindOverrides();
  setTimeout(bindOverrides, 500);
})();
