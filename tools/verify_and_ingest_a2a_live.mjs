#!/usr/bin/env node
import fs from 'node:fs';
import crypto from 'node:crypto';

const REGISTRY_BASE = 'https://api.a2a-registry.org';
const CARD_PATH = '/.well-known/agent-card.json';
const EXPECTED_NAME = 'JANUS Machine Market A2A Gateway';

function fail(code, detail = '') {
  const suffix = detail ? `:${detail}` : '';
  throw new Error(`${code}${suffix}`);
}

function sha256(value) {
  const bytes = typeof value === 'string' ? value : JSON.stringify(value);
  return crypto.createHash('sha256').update(bytes).digest('hex');
}

function parseArgs(argv) {
  const out = { ingest: false, output: null, baseUrl: null };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--ingest') out.ingest = true;
    else if (arg === '--base-url') out.baseUrl = argv[++i];
    else if (arg === '--output') out.output = argv[++i];
    else fail('UNKNOWN_ARGUMENT', arg);
  }
  if (!out.baseUrl) fail('BASE_URL_REQUIRED');
  return out;
}

function canonicalBaseUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    fail('BASE_URL_INVALID');
  }
  if (url.protocol !== 'https:') fail('BASE_URL_MUST_BE_HTTPS');
  if (url.username || url.password || url.search || url.hash) fail('BASE_URL_CREDENTIALS_QUERY_FRAGMENT_FORBIDDEN');
  url.pathname = url.pathname.replace(/\/+$/, '') || '/';
  if (url.pathname !== '/') fail('BASE_URL_MUST_BE_ORIGIN_ONLY');
  return url.origin;
}

async function getJson(url, init = {}) {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      'User-Agent': 'JANUS-A2A-Live-Gate/1.0',
      ...(init.headers || {}),
    },
    signal: AbortSignal.timeout(15000),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    fail('NON_JSON_RESPONSE', `${response.status}:${url}`);
  }
  return { response, json, text };
}

function verifyAgentCard(card, baseUrl) {
  if (!card || typeof card !== 'object' || Array.isArray(card)) fail('AGENT_CARD_INVALID_OBJECT');
  if (card.name !== EXPECTED_NAME) fail('AGENT_CARD_NAME_MISMATCH');
  if (!Array.isArray(card.supportedInterfaces) || card.supportedInterfaces.length !== 1) {
    fail('AGENT_CARD_INTERFACE_COUNT_INVALID');
  }
  const iface = card.supportedInterfaces[0];
  if (iface.protocolBinding !== 'HTTP+JSON') fail('AGENT_CARD_BINDING_INVALID');
  if (iface.protocolVersion !== '1.0') fail('AGENT_CARD_PROTOCOL_VERSION_INVALID');
  if ((iface.tenant ?? '') !== '') fail('AGENT_CARD_TENANT_UNEXPECTED');
  if (iface.url !== `${baseUrl}/a2a/rest`) fail('AGENT_CARD_INTERFACE_URL_MISMATCH');
  if (card.capabilities?.streaming !== false) fail('AGENT_CARD_STREAMING_MUST_BE_FALSE');
  if (card.capabilities?.pushNotifications !== false) fail('AGENT_CARD_PUSH_MUST_BE_FALSE');
  if (card.capabilities?.extendedAgentCard !== false) fail('AGENT_CARD_EXTENDED_MUST_BE_FALSE');
  if (!Array.isArray(card.skills) || card.skills.map((x) => x.id).join(',') !== 'janus-discovery-ingress') {
    fail('AGENT_CARD_SKILL_SET_INVALID');
  }
  if ((card.securityRequirements || []).length !== 0) fail('AGENT_CARD_UNEXPECTED_SECURITY_REQUIREMENTS');
  return iface;
}

function extractGatewayPayload(sendResponse) {
  const message = sendResponse?.message;
  if (!message || !Array.isArray(message.parts) || !message.parts.length) fail('A2A_SEND_MESSAGE_RESPONSE_MISSING');
  const part = message.parts[0];
  const text = part.text ?? part?.content?.value ?? part?.content?.text;
  if (typeof text !== 'string') fail('A2A_SEND_MESSAGE_TEXT_MISSING');
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    fail('A2A_GATEWAY_PAYLOAD_NOT_JSON');
  }
  if (payload.gateway_role !== 'A2A_DISCOVERY_AND_INGRESS_BRIDGE_NOT_SEARCH_EXECUTOR') {
    fail('A2A_GATEWAY_ROLE_INVALID');
  }
  if (payload.source_discovery_surface !== 'GLOBAL_A2A_REGISTRY') fail('A2A_DISCOVERY_SURFACE_INVALID');
  for (const key of ['execution_started', 'payment_authority', 'command_authority', 'repository_write_authority', 'external_effect_authority']) {
    if (payload.authority?.[key] !== false) fail('A2A_AUTHORITY_CEILING_BROKEN', key);
  }
  if (payload.truth_requirements?.gateway_does_not_receive_or_store_caller_github_credential !== true) {
    fail('A2A_CALLER_IDENTITY_FIREWALL_MISSING');
  }
  return payload;
}

function recursiveContains(value, needle) {
  if (typeof value === 'string') return value === needle || value.includes(needle);
  if (Array.isArray(value)) return value.some((item) => recursiveContains(item, needle));
  if (value && typeof value === 'object') return Object.values(value).some((item) => recursiveContains(item, needle));
  return false;
}

async function verifyPublicListing(cardUrl) {
  const queries = ['JANUS Machine Market A2A Gateway', 'JANUS'];
  const observations = [];
  for (const q of queries) {
    const url = `${REGISTRY_BASE}/public/agents?q=${encodeURIComponent(q)}`;
    const { response, json } = await getJson(url);
    observations.push({ q, status: response.status, response_hash: sha256(json) });
    if (response.ok && (recursiveContains(json, cardUrl) || recursiveContains(json, EXPECTED_NAME))) {
      return { listed: true, query: q, public_search_response: json, observations };
    }
  }
  return { listed: false, query: null, public_search_response: null, observations };
}

async function main() {
  const args = parseArgs(process.argv);
  const baseUrl = canonicalBaseUrl(args.baseUrl);
  const cardUrl = `${baseUrl}${CARD_PATH}`;

  const cardFetch = await getJson(cardUrl);
  if (!cardFetch.response.ok) fail('AGENT_CARD_FETCH_FAILED', String(cardFetch.response.status));
  const iface = verifyAgentCard(cardFetch.json, baseUrl);

  const messageId = `janus-live-gate-${crypto.randomUUID()}`;
  const send = await getJson(`${baseUrl}/a2a/rest/message:send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/a2a+json',
      'A2A-Version': '1.0',
    },
    body: JSON.stringify({
      message: {
        messageId,
        role: 'ROLE_USER',
        parts: [{ text: 'Return the JANUS machine ingress package for an external machine discovered through the Global A2A Registry.' }],
      },
    }),
  });
  if (!send.response.ok) fail('A2A_SEND_MESSAGE_FAILED', String(send.response.status));
  const payload = extractGatewayPayload(send.json);

  let listing = await verifyPublicListing(cardUrl);
  let ingest = null;
  if (args.ingest) {
    if (listing.listed) {
      ingest = {
        status: 'ALREADY_LISTED_NO_POST',
        response: null,
        response_hash: null,
      };
    } else {
      const ingestResult = await getJson(`${REGISTRY_BASE}/public/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manifestUrl: cardUrl }),
      });
      if (!ingestResult.response.ok) fail('GLOBAL_A2A_REGISTRY_INGEST_FAILED', String(ingestResult.response.status));
      ingest = {
        status: ingestResult.response.status,
        response: ingestResult.json,
        response_hash: sha256(ingestResult.json),
      };
      listing = await verifyPublicListing(cardUrl);
      for (let attempt = 1; attempt <= 12 && !listing.listed; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 5000));
        listing = await verifyPublicListing(cardUrl);
      }
    }
  }
  if (args.ingest && !listing.listed) fail('GLOBAL_A2A_REGISTRY_LISTING_NOT_OBSERVED_AFTER_INGEST');

  const body = {
    schema: 'janus.machine_market.a2a_live_registry_receipt.v1',
    status: args.ingest ? 'A2A_LIVE_AND_GLOBAL_REGISTRY_LISTED' : 'A2A_LIVE_VERIFIED_REGISTRY_NOT_MUTATED',
    observed_at: new Date().toISOString(),
    a2a: {
      base_url: baseUrl,
      agent_card_url: cardUrl,
      agent_card_sha256: sha256(cardFetch.json),
      interface: iface,
      send_message_status: send.response.status,
      send_message_response_sha256: sha256(send.json),
      gateway_payload_sha256: sha256(payload),
      official_protocol_version: '1.0',
      binding: 'HTTP+JSON',
      https_verified: true,
    },
    registry: {
      ingest_requested: args.ingest,
      ingest,
      public_listing_observed: listing.listed,
      public_listing_query: listing.query,
      public_listing_response_sha256: listing.public_search_response ? sha256(listing.public_search_response) : null,
      observations: listing.observations,
    },
    authority: {
      money_enabled: false,
      payment_authority: false,
      command_authority: false,
      execution_witness: false,
      foreign_agent_witness: false,
    },
    laws: [
      'A2A_RUNTIME_LIVE != R1E_FOREIGN_AGENT_WITNESS',
      'GLOBAL_A2A_REGISTRY_LISTED != EXECUTION_WITNESS',
      'REGISTRY_DISCOVERY != PURCHASE_AUTHORITY',
      'REGISTRY_RETRY_MUST_RECOVER_FROM_ALREADY_LISTED_WITHOUT_SECOND_POST',
    ],
  };
  body.receipt_hash = sha256(body);
  const rendered = `${JSON.stringify(body, null, 2)}\n`;
  if (args.output) fs.writeFileSync(args.output, rendered, 'utf8');
  process.stdout.write(rendered);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
