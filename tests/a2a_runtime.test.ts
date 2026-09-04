import request from 'supertest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { app, buildAgentCard, buildIngressPackage } from '../src/index.js';

function publicJson(url: string) {
  if (url.endsWith('/MACHINE_INGRESS.json')) {
    return {
      live_services: {
        'JANUS.SEARCH': { status: 'LIVE_PUBLIC_ZERO_PRICE_BETA_PLUS_OWNER_SHADOW' },
      },
      current_commerce_state: {
        money_enabled: false,
        inference: 'CLOSED',
        compute: 'CLOSED',
      },
    };
  }
  if (url.endsWith('/FOREIGN_AGENT_WITNESS.json')) {
    return { foreign_agent_witness: false };
  }
  throw new Error(`unexpected fixture URL ${url}`);
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      return new Response(JSON.stringify(publicJson(url)), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('JANUS A2A v1 Agent Card', () => {
  it('publishes exactly one truthful HTTP+JSON 1.0 interface', () => {
    const card = buildAgentCard({
      VERCEL_ENV: 'production',
      VERCEL_PROJECT_PRODUCTION_URL: 'janus-a2a.vercel.app',
    });
    expect(card.supportedInterfaces).toEqual([
      {
        url: 'https://janus-a2a.vercel.app/a2a/rest',
        protocolBinding: 'HTTP+JSON',
        tenant: '',
        protocolVersion: '1.0',
      },
    ]);
    expect(card.capabilities).toBeDefined();
    const capabilities = card.capabilities!;
    expect(capabilities.streaming).toBe(false);
    expect(capabilities.pushNotifications).toBe(false);
    expect(capabilities.extendedAgentCard).toBe(false);
    expect(card.skills.map((skill) => skill.id)).toEqual(['janus-discovery-ingress']);
    expect(card.skills[0].description).toContain('does not itself execute JANUS.SEARCH');
  });

  it('fails closed if a production interface is explicitly non-HTTPS', () => {
    expect(() =>
      buildAgentCard({
        VERCEL_ENV: 'production',
        JANUS_A2A_PUBLIC_BASE_URL: 'http://example.test',
      }),
    ).toThrow('A2A_PRODUCTION_INTERFACE_MUST_BE_HTTPS');
  });

  it('serves the canonical well-known Agent Card', async () => {
    const response = await request(app).get('/.well-known/agent-card.json').expect(200);
    expect(response.body.name).toBe('JANUS Machine Market A2A Gateway');
    expect(response.body.supportedInterfaces[0].protocolBinding).toBe('HTTP+JSON');
    expect(response.body.supportedInterfaces[0].protocolVersion).toBe('1.0');
  });
});

describe('JANUS A2A ingress package', () => {
  it('returns caller-authenticated GitHub ingress without granting authority', async () => {
    const result = await buildIngressPackage('Find A2A discovery evidence', 'msg-123');
    expect(result.status).toBe('READY_FOR_CALLER_AUTHENTICATED_SUBMISSION');
    expect(result.source_discovery_surface).toBe('GLOBAL_A2A_REGISTRY');
    expect(result.gateway_role).toBe('A2A_DISCOVERY_AND_INGRESS_BRIDGE_NOT_SEARCH_EXECUTOR');

    const ingress = result.janus_search_ingress as Record<string, unknown>;
    expect(ingress.endpoint).toBe(
      'https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues',
    );
    expect(ingress.authentication).toBe('CALLER_SUPPLIED_GITHUB_CREDENTIAL_WITH_ISSUES_WRITE');
    expect(String(ingress.body)).toContain('GLOBAL_A2A_REGISTRY');
    expect(String(ingress.body)).toContain('JANUS_DISCOVERY_WITNESS_JSON');
    expect(String(ingress.body)).toContain('JANUS_BUYER_QUERY_SHADOW_JSON');

    const authority = result.authority as Record<string, unknown>;
    expect(authority.execution_started).toBe(false);
    expect(authority.payment_authority).toBe(false);
    expect(authority.command_authority).toBe(false);
    expect(authority.repository_write_authority).toBe(false);
    expect(authority.external_effect_authority).toBe(false);
  });

  it('rejects oversized or HTML-comment-breaking input before constructing ingress', async () => {
    expect((await buildIngressPackage('x'.repeat(4001), 'big')).status).toBe('REJECTED_LOCALLY');
    expect((await buildIngressPackage('bad --> marker', 'marker')).status).toBe('REJECTED_LOCALLY');
  });

  it('fails closed when public Market state cannot be fetched', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('no', { status: 503 })));
    const result = await buildIngressPackage('Find evidence', 'msg-fail');
    expect(result.status).toBe('UNAVAILABLE_FAIL_CLOSED');
    const current = result.current_public_state as Record<string, unknown>;
    expect(current.foreign_agent_witness).toBeNull();
    expect(current.money_enabled).toBe(false);
  });
});

describe('A2A HTTP+JSON surface', () => {
  it('accepts a v1 SendMessage request and returns a direct agent Message', async () => {
    const response = await request(app)
      .post('/a2a/rest/message:send')
      .set('A2A-Version', '1.0')
      .set('Content-Type', 'application/a2a+json')
      .send({
        message: {
          messageId: 'external-machine-msg-1',
          role: 'ROLE_USER',
          parts: [{ text: 'How can my machine call JANUS.SEARCH?' }],
        },
      })
      .expect(200);

    expect(response.body.message).toBeTruthy();
    const text = response.body.message.parts[0].text;
    const payload = JSON.parse(text);
    expect(payload.source_discovery_surface).toBe('GLOBAL_A2A_REGISTRY');
    expect(payload.authority.execution_started).toBe(false);
    expect(payload.authority.command_authority).toBe(false);
  });

  it('rejects streaming because the Agent Card declares streaming=false', async () => {
    const response = await request(app)
      .post('/a2a/rest/message:stream')
      .set('A2A-Version', '1.0')
      .set('Content-Type', 'application/a2a+json')
      .send({
        message: {
          messageId: 'external-machine-msg-stream',
          role: 'ROLE_USER',
          parts: [{ text: 'stream please' }],
        },
      })
      .expect(400);
    expect(JSON.stringify(response.body)).toContain('UNSUPPORTED_OPERATION');
  });
});
