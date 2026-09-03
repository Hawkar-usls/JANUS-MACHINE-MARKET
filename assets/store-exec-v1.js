(() => {
  'use strict';

  const HOME_REPOSITORY = 'Hawkar-usls/Hawkar-usls';
  const MARKET_REPOSITORY = 'Hawkar-usls/JANUS-MACHINE-MARKET';

  const LIVE_HOME_SERVICES = {
    'JANUS.SEARCH': {
      label: 'JANUS.SEARCH',
      titlePrefix: '[JANUS R1B BUYER QUERY SHADOW]',
      marker: 'JANUS_BUYER_QUERY_SHADOW_JSON',
      schema: 'janus.machine_market.buyer_query_shadow_request.v1',
      lane: 'PERSISTENT_JANUS_CONVERSATION',
      publicBeta: true
    },
    'JANUS.REPO_AUDIT': {
      label: 'JANUS.REPO_AUDIT',
      titlePrefix: '[JANUS REPO AUDIT SHADOW]',
      marker: 'JANUS_REPO_AUDIT_SHADOW_JSON',
      schema: 'janus.machine_market.repo_audit_pages_request.v1',
      lane: 'PERSISTENT_JANUS_REPOSITORY_AUDIT',
      publicBeta: false
    },
    'JANUS.DATASET_SCOUT': {
      label: 'JANUS.DATASET_SCOUT',
      titlePrefix: '[JANUS DATASET SCOUT SHADOW]',
      marker: 'JANUS_DATASET_SCOUT_SHADOW_JSON',
      schema: 'janus.machine_market.dataset_scout_pages_request.v1',
      lane: 'PERSISTENT_JANUS_DATASET_SCOUT',
      publicBeta: false
    }
  };

  function q(sel) { return document.querySelector(sel); }

  function loadout() {
    try { return Array.isArray(state.loadout) ? state.loadout : []; }
    catch (_) { return []; }
  }

  function liveItems() {
    return loadout().filter(item => LIVE_HOME_SERVICES[item.sku]);
  }

  function newId(prefix) {
    let principal = 'pages';
    try {
      principal = String(state.profile?.agent_id || 'pages').replace(/[^a-zA-Z0-9_.:-]/g, '-').slice(0, 80);
    } catch (_) {}
    let nonce;
    try { nonce = crypto.randomUUID(); }
    catch (_) { nonce = `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
    return `${prefix}-${principal}-${nonce}`;
  }

  function needText(promptText = 'What task should the running JANUS handle?') {
    const field = q('#needInput');
    let text = String(field?.value || '').trim();
    if (!text) {
      text = String(window.prompt(promptText, '') || '').trim();
      if (text && field) field.value = text;
    }
    return text;
  }

  function normalizeRepository(value) {
    let text = String(value || '').trim();
    if (!text) return '';
    text = text.replace(/^https?:\/\/github\.com\//i, '').replace(/\.git$/i, '').replace(/^\/+|\/+$/g, '');
    const match = text.match(/^([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$/);
    return match ? `${match[1]}/${match[2]}` : '';
  }

  function buildSearchRequest(item) {
    const message = needText();
    if (!message) return { error: 'TASK_TEXT_REQUIRED' };
    const turns = Math.max(1, Math.min(8, Number(item.qty || 1)));
    return {
      schema: LIVE_HOME_SERVICES['JANUS.SEARCH'].schema,
      conversation_id: newId('market'),
      turn_index: 0,
      message_text: message,
      max_turns: turns,
      max_message_utf8_bytes: 8000,
      max_answer_utf8_bytes: 12000,
      conversation_history_turns: Math.min(8, Math.max(0, turns - 1))
    };
  }

  function buildRepoAuditRequest(item) {
    let repository = normalizeRepository(q('#needInput')?.value || '');
    if (!repository) {
      repository = normalizeRepository(window.prompt('Repository to audit (owner/repo or GitHub URL)', 'Hawkar-usls/JANUS-MACHINE-MARKET') || '');
    }
    if (!repository) return { error: 'REPOSITORY_REQUIRED' };
    let ref = String(window.prompt('Git ref to audit', 'main') || 'main').trim();
    if (!ref) ref = 'main';
    const qty = Math.max(1, Math.min(4, Number(item.qty || 1)));
    return {
      schema: LIVE_HOME_SERVICES['JANUS.REPO_AUDIT'].schema,
      repository,
      ref,
      max_tree_entries: Math.min(5000, 1250 * qty),
      max_blob_files: Math.min(24, 6 * qty),
      max_total_blob_bytes: Math.min(750000, 187500 * qty),
      requested_mode: String(item.mode || 'ARCHITECTURE')
    };
  }

  function buildDatasetScoutRequest(item) {
    const query = needText('What public dataset should JANUS find?');
    if (!query) return { error: 'DATASET_QUERY_REQUIRED' };
    const qty = Math.max(1, Math.min(8, Number(item.qty || 1)));
    return {
      schema: LIVE_HOME_SERVICES['JANUS.DATASET_SCOUT'].schema,
      query,
      domain: '',
      date_range: null,
      license_preferences: [],
      format_preferences: [],
      max_results: qty,
      max_catalogs: 2,
      per_catalog_timeout_seconds: 8,
      requested_mode: String(item.mode || 'DISCOVERY')
    };
  }

  function buildRequest(item) {
    if (!item) return null;
    if (item.sku === 'JANUS.SEARCH') return buildSearchRequest(item);
    if (item.sku === 'JANUS.REPO_AUDIT') return buildRepoAuditRequest(item);
    if (item.sku === 'JANUS.DATASET_SCOUT') return buildDatasetScoutRequest(item);
    return null;
  }

  function canonicalPayloadForWorkflow(item, request) {
    // The issue-side adapters deliberately accept only a bounded subset. Extra
    // Pages metadata is stripped here instead of asking HOME to trust UI fields.
    if (item.sku === 'JANUS.REPO_AUDIT') {
      return {
        repository: request.repository,
        ref: request.ref,
        max_tree_entries: request.max_tree_entries,
        max_blob_files: request.max_blob_files,
        max_total_blob_bytes: request.max_total_blob_bytes
      };
    }
    if (item.sku === 'JANUS.DATASET_SCOUT') {
      return {
        query: request.query,
        domain: request.domain,
        date_range: request.date_range,
        license_preferences: request.license_preferences,
        format_preferences: request.format_preferences,
        max_results: request.max_results,
        max_catalogs: request.max_catalogs,
        per_catalog_timeout_seconds: request.per_catalog_timeout_seconds
      };
    }
    return request;
  }

  function issueBody(item, request) {
    const svc = LIVE_HOME_SERVICES[item.sku];
    const payload = canonicalPayloadForWorkflow(item, request);
    const ingressNote = svc.publicBeta
      ? 'JANUS.SEARCH is open as a bounded zero-price GitHub-authenticated public beta. External requests are server-normalized to one turn, 4 KB input / 6 KB output and quota limits before entering the HOME outbox. Repository-owner requests continue through the existing owner-shadow contract.'
      : 'This service currently uses the repository-owner shadow ingress. It is not yet open as a public service.';
    return [
      `## JANUS MACHINE MARKET · ${svc.label} task handoff to the running JANUS`,
      '',
      ingressNote,
      '',
      'Route:',
      '`Pages -> Market issue -> create-only Market outbox -> credentialless HOME pull -> Activator -> persistent JANUS organ -> HOME response -> credentialless Market reconcile -> this issue`',
      '',
      `- service: \`${svc.label}\``,
      `- lane: \`${svc.lane}\``,
      `- public_zero_price_beta: \`${svc.publicBeta ? 'true' : 'false'}\``,
      '- price: `0`',
      '- payment_required: `false`',
      '- money_enabled: `false`',
      '- command_authority_granted: `false`',
      '- external_effect_authorized: `false`',
      `- HOME repository: \`${HOME_REPOSITORY}\``,
      '',
      `<!-- ${svc.marker}`,
      JSON.stringify(payload, null, 2),
      `${svc.marker} -->`,
      '',
      '`PUBLIC INTAKE != COMPLETED SERVICE · BUYER QUERY != COMMAND · PURCHASE GRANT != EXECUTION AUTHORITY`'
    ].join('\n');
  }

  function validateSingleLiveItem() {
    const items = liveItems();
    if (!items.length) return { error: 'NO_LIVE_HOME_SERVICE' };
    if (items.length > 1) return { error: 'MULTI_SERVICE_NOT_YET_ATOMIC', items };
    return { item: items[0] };
  }

  async function copyJanusTask() {
    const selected = validateSingleLiveItem();
    if (selected.error === 'NO_LIVE_HOME_SERVICE') return alert('Add JANUS.SEARCH, JANUS.REPO_AUDIT, or JANUS.DATASET_SCOUT to the loadout first.');
    if (selected.error === 'MULTI_SERVICE_NOT_YET_ATOMIC') return alert('For the live R1 contour, submit one executable service per trade. Multi-SKU atomic orchestration is not admitted yet.');
    const request = buildRequest(selected.item);
    if (!request || request.error) return alert('Complete the task parameters first.');
    await navigator.clipboard.writeText(JSON.stringify({ sku: selected.item.sku, request: canonicalPayloadForWorkflow(selected.item, request) }, null, 2));
    try { recordActivity('JANUS_TASK', `${selected.item.sku} HOME task JSON copied`); } catch (_) {}
    alert(`${selected.item.sku} task JSON copied.`);
  }

  function openJanusTask() {
    const selected = validateSingleLiveItem();
    if (selected.error === 'NO_LIVE_HOME_SERVICE') return alert('Add JANUS.SEARCH, JANUS.REPO_AUDIT, or JANUS.DATASET_SCOUT to the loadout first.');
    if (selected.error === 'MULTI_SERVICE_NOT_YET_ATOMIC') return alert('For the live R1 contour, submit one executable service per trade. Multi-SKU atomic orchestration is not admitted yet.');
    const item = selected.item;
    const request = buildRequest(item);
    if (!request || request.error) return alert('Complete the task parameters first.');
    const svc = LIVE_HOME_SERVICES[item.sku];
    const title = `${svc.titlePrefix} Pages Market task`;
    const url = `https://github.com/${MARKET_REPOSITORY}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(issueBody(item, request))}`;
    try { recordActivity('JANUS_TASK', `${item.sku} persistent HOME task issue composer opened`, { sku: item.sku }); } catch (_) {}
    window.open(url, '_blank', 'noopener');
  }

  window.shadowRequest = function shadowRequestR1E() {
    const selected = validateSingleLiveItem();
    if (selected.error) return selected;
    return buildRequest(selected.item);
  };
  window.copyShadow = copyJanusTask;
  window.openShadow = openJanusTask;

  window.configureTradeActions = function configureTradeActionsR1E() {
    const items = liveItems();
    const hasHelios = loadout().some(item => item.sku === 'HELIOS.PILOT');
    const copy = q('#copyShadow');
    const primary = q('#openShadow');
    const rule = q('.trade-rule');
    if (!copy || !primary) return;

    copy.hidden = items.length === 0;
    copy.textContent = 'COPY JANUS TASK JSON';
    copy.onclick = copyJanusTask;
    primary.disabled = false;

    if (items.length === 1) {
      const item = items[0];
      const svc = LIVE_HOME_SERVICES[item.sku];
      primary.textContent = svc.publicBeta
        ? `SEND ${item.sku} · ZERO-PRICE PUBLIC BETA`
        : `SEND ${item.sku} · OWNER SHADOW`;
      primary.onclick = openJanusTask;
      if (rule && svc.publicBeta) rule.innerHTML = `<b>PUBLIC BETA:</b> ${item.sku} can be submitted by a GitHub-authenticated external requester. The Market server clamps it to one bounded turn, writes a create-only packet, persistent JANUS HOME answers it, and Market returns the verified response to the same issue. Payments, command authority and external effects remain disabled.`;
      else if (rule) rule.innerHTML = `<b>OWNER SHADOW:</b> ${item.sku} uses the proven Market -> persistent JANUS HOME route but is not open to external requesters yet.`;
    } else if (items.length > 1) {
      primary.textContent = 'SPLIT LIVE SERVICES INTO SEPARATE TASKS';
      primary.disabled = true;
      primary.onclick = null;
      if (rule) rule.innerHTML = '<b>R1 ATOMICITY:</b> multiple live HOME services are present in this loadout. Submit them one at a time until a proof-carrying multi-SKU orchestration grant exists.';
    } else if (hasHelios) {
      primary.textContent = 'VIEW HELIOS PILOT AUTHORITY';
      primary.onclick = () => window.open('https://github.com/Hawkar-usls/Janus-HELIOS', '_blank', 'noopener');
      if (rule) rule.textContent = 'HELIOS.PILOT remains delegated to its separate canonical authority.';
    } else {
      primary.textContent = 'CURRENT SKU IS PREVIEW-ONLY';
      primary.disabled = true;
      primary.onclick = null;
      if (rule) rule.textContent = 'No selected SKU currently has a Pages-to-HOME execution ingress. Public now: JANUS.SEARCH zero-price beta. Owner-shadow only: JANUS.REPO_AUDIT and JANUS.DATASET_SCOUT.';
    }
  };

  function patchVisibleTruth() {
    const truthbar = q('#truthbar');
    if (truthbar && !truthbar.querySelector('.truth.public-search-beta')) {
      const chip = document.createElement('span');
      chip.className = 'truth live public-search-beta';
      chip.innerHTML = 'SEARCH <b>PUBLIC BETA</b>';
      truthbar.insertBefore(chip, truthbar.children[2] || null);
    }
    if (truthbar && !truthbar.querySelector('.truth.home-bridge')) {
      const chip = document.createElement('span');
      chip.className = 'truth live home-bridge';
      chip.innerHTML = 'JANUS HOME <b>3 R1 LANES</b>';
      truthbar.insertBefore(chip, truthbar.children[3] || null);
    }
    const status = q('#status .status-grid');
    if (status && !status.querySelector('[data-r1d-home]')) {
      const card = document.createElement('article');
      card.className = 'panel';
      card.dataset.r1dHome = 'true';
      card.innerHTML = '<p class="eyebrow">TASK EXECUTION</p><h2>Market → persistent JANUS</h2><p>JANUS.SEARCH is the first GitHub-authenticated zero-price public beta routed to persistent JANUS HOME. REPO_AUDIT and DATASET_SCOUT remain owner-shadow until a real external SEARCH roundtrip is sealed.</p><b class="status-big cyan">SEARCH BETA</b>';
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
