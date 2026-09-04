import express from 'express';
import {
  A2A_PROTOCOL_VERSION,
  AGENT_CARD_PATH,
  type AgentCard,
  type Message,
  Role,
} from '@a2a-js/sdk';
import {
  AgentEvent,
  type AgentExecutor,
  DefaultRequestHandler,
  type ExecutionEventBus,
  InMemoryTaskStore,
  type RequestContext,
} from '@a2a-js/sdk/server';
import {
  agentCardHandler,
  restHandler,
  UserBuilder,
} from '@a2a-js/sdk/server/express';

const MARKET_REPOSITORY = 'https://github.com/Hawkar-usls/JANUS-MACHINE-MARKET';
const MARKET_API = 'https://api.github.com/repos/Hawkar-usls/JANUS-MACHINE-MARKET/issues';
const RAW_MAIN = 'https://raw.githubusercontent.com/Hawkar-usls/JANUS-MACHINE-MARKET/main';
const MAX_QUERY_BYTES = 4000;

export function publicBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  const explicit = String(env.JANUS_A2A_PUBLIC_BASE_URL || '').trim();
  if (explicit) return explicit.replace(/\/$/, '');
  const production = String(env.VERCEL_PROJECT_PRODUCTION_URL || '').trim();
  if (production) return `https://${production.replace(/\/$/, '')}`;
  return 'http://127.0.0.1:3000';
}

export function buildAgentCard(env: NodeJS.ProcessEnv = process.env): AgentCard {
  const base = publicBaseUrl(env);
  if (env.VERCEL_ENV === 'production' && !base.startsWith('https://')) {
    throw new Error('A2A_PRODUCTION_INTERFACE_MUST_BE_HTTPS');
  }
  return {
    name: 'JANUS Machine Market A2A Gateway',
    description:
      'Public A2A v1 gateway for discovering JANUS capabilities and obtaining a bounded, identity-preserving JANUS.SEARCH ingress package. The gateway does not accept payment and does not impersonate the external caller.',
    supportedInterfaces: [
      {
        url: `${base}/a2a/rest`,
        protocolBinding: 'HTTP+JSON',
        tenant: '',
        protocolVersion: A2A_PROTOCOL_VERSION,
      },
    ],
    provider: {
      organization: 'Hawkar-usls',
      url: 'https://hawkar-usls.github.io/JANUS-MACHINE-MARKET/',
    },
    version: '0.1.0',
    documentationUrl: MARKET_REPOSITORY,
    capabilities: {
      streaming: false,
      pushNotifications: false,
      extendedAgentCard: false,
      extensions: [],
    },
    securitySchemes: {},
    securityRequirements: [],
    defaultInputModes: ['text/plain'],
    defaultOutputModes: ['text/plain'],
    skills: [
      {
        id: 'janus-discovery-ingress',
        name: 'Discover JANUS and prepare a SEARCH ingress package',
        description:
          'Returns current public JANUS capability state, the exact caller-authenticated GitHub ingress for zero-price JANUS.SEARCH, and a Global A2A Registry discovery-witness template. It does not itself execute JANUS.SEARCH or grant commerce authority.',
        tags: [
          'janus',
          'research',
          'search',
          'evidence',
          'provenance',
          'agent-discovery',
          'github-ingress',
        ],
        examples: [
          'What can JANUS do and how can my machine call JANUS.SEARCH?',
          'Prepare a bounded JANUS.SEARCH request for: find evidence about A2A agent discovery.',
        ],
        inputModes: ['text/plain'],
        outputModes: ['text/plain'],
        securityRequirements: [],
      },
    ],
    signatures: [],
  };
}

function extractText(message: Message): string {
  const text = message.parts
    .filter((part) => part.content?.$case === 'text')
    .map((part) => (part.content?.$case === 'text' ? part.content.value : ''))
    .join('\n')
    .trim();
  return text;
}

async function fetchPublicJson(path: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${RAW_MAIN}/${path}`, {
    headers: { Accept: 'application/json', 'User-Agent': 'JANUS-A2A-Gateway/0.1' },
    signal: AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`UPSTREAM_${path}_${response.status}`);
  const value = await response.json();
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`UPSTREAM_${path}_INVALID_JSON_OBJECT`);
  }
  return value as Record<string, unknown>;
}

function markerBlock(marker: string, payload: Record<string, unknown>): string {
  return `<!-- ${marker}\n${JSON.stringify(payload, null, 2)}\n${marker} -->`;
}

export async function buildIngressPackage(
  query: string,
  messageId: string,
): Promise<Record<string, unknown>> {
  const queryBytes = Buffer.byteLength(query, 'utf8');
  if (!query || queryBytes > MAX_QUERY_BYTES || query.includes('-->')) {
    return {
      schema: 'janus.machine_market.a2a_ingress_package.v1',
      status: 'REJECTED_LOCALLY',
      reason: !query
        ? 'EMPTY_QUERY'
        : queryBytes > MAX_QUERY_BYTES
          ? 'QUERY_EXCEEDS_4000_UTF8_BYTES'
          : 'HTML_COMMENT_TERMINATOR_FORBIDDEN',
      execution_started: false,
      money_enabled: false,
    };
  }

  let ingress: Record<string, unknown> | null = null;
  let foreignWitness: Record<string, unknown> | null = null;
  let upstreamStatus = 'AVAILABLE';
  try {
    [ingress, foreignWitness] = await Promise.all([
      fetchPublicJson('MACHINE_INGRESS.json'),
      fetchPublicJson('FOREIGN_AGENT_WITNESS.json'),
    ]);
  } catch {
    upstreamStatus = 'UNAVAILABLE_FAIL_CLOSED';
  }

  const conversationId = `a2a-${messageId.replace(/[^A-Za-z0-9._-]/g, '-').slice(0, 96)}`;
  const discoveryClaim = {
    schema: 'janus.machine_market.foreign_discovery_claim.v1',
    discovery_surface: 'GLOBAL_A2A_REGISTRY',
    independent_from_owner: true,
    machine_client: true,
  };
  const searchRequest = {
    schema: 'janus.machine_market.buyer_query_shadow_request.v1',
    conversation_id: conversationId,
    turn_index: 0,
    message_text: query,
  };
  const issueBody = `${markerBlock('JANUS_DISCOVERY_WITNESS_JSON', discoveryClaim)}\n\n${markerBlock('JANUS_BUYER_QUERY_SHADOW_JSON', searchRequest)}`;

  const liveServices = (ingress?.live_services || {}) as Record<string, unknown>;
  const search = (liveServices['JANUS.SEARCH'] || {}) as Record<string, unknown>;
  const commerce = (ingress?.current_commerce_state || {}) as Record<string, unknown>;

  return {
    schema: 'janus.machine_market.a2a_ingress_package.v1',
    status: upstreamStatus === 'AVAILABLE' ? 'READY_FOR_CALLER_AUTHENTICATED_SUBMISSION' : upstreamStatus,
    gateway_role: 'A2A_DISCOVERY_AND_INGRESS_BRIDGE_NOT_SEARCH_EXECUTOR',
    a2a_protocol_version: A2A_PROTOCOL_VERSION,
    source_discovery_surface: 'GLOBAL_A2A_REGISTRY',
    current_public_state: {
      upstream_status: upstreamStatus,
      janus_search_status: search.status ?? null,
      foreign_agent_witness: foreignWitness?.foreign_agent_witness ?? null,
      money_enabled: commerce.money_enabled ?? false,
      inference: commerce.inference ?? 'CLOSED',
      compute: commerce.compute ?? 'CLOSED',
    },
    janus_search_ingress: {
      transport: 'github_issues_rest',
      method: 'POST',
      endpoint: MARKET_API,
      authentication: 'CALLER_SUPPLIED_GITHUB_CREDENTIAL_WITH_ISSUES_WRITE',
      title: '[JANUS R1B BUYER QUERY SHADOW] External A2A-discovered SEARCH request',
      body: issueBody,
      response_tracking: `${MARKET_API}/{issue_number}/comments`,
    },
    truth_requirements: {
      caller_must_use_own_github_identity: true,
      set_independent_from_owner_true_only_if_factually_true: true,
      set_machine_client_true_only_if_factually_true: true,
      gateway_does_not_receive_or_store_caller_github_credential: true,
    },
    authority: {
      execution_started: false,
      payment_required: false,
      payment_authority: false,
      command_authority: false,
      repository_write_authority: false,
      external_effect_authority: false,
    },
    canonical_repository: MARKET_REPOSITORY,
  };
}

class JanusA2AGatewayExecutor implements AgentExecutor {
  public cancelTask = async (_taskId: string, _eventBus: ExecutionEventBus): Promise<void> => {};

  async execute(requestContext: RequestContext, eventBus: ExecutionEventBus): Promise<void> {
    const query = extractText(requestContext.userMessage);
    const result = await buildIngressPackage(query, requestContext.userMessage.messageId);
    const finalMessage: Message = {
      messageId: crypto.randomUUID(),
      role: Role.ROLE_AGENT,
      parts: [
        {
          content: { $case: 'text', value: JSON.stringify(result) },
          metadata: undefined,
          filename: 'janus-a2a-ingress-package.json',
          mediaType: 'text/plain',
        },
      ],
      taskId: requestContext.taskId,
      contextId: requestContext.contextId,
      extensions: [],
      metadata: {},
      referenceTaskIds: [],
    };
    eventBus.publish(AgentEvent.message(finalMessage));
  }
}

const agentCard = buildAgentCard();
const requestHandler = new DefaultRequestHandler(
  agentCard,
  new InMemoryTaskStore(),
  new JanusA2AGatewayExecutor(),
);

const app = express();
app.disable('x-powered-by');
app.get('/healthz', (_req, res) => {
  res.json({
    status: 'ok',
    a2aProtocolVersion: A2A_PROTOCOL_VERSION,
    role: 'DISCOVERY_AND_INGRESS_BRIDGE',
    moneyEnabled: false,
  });
});
app.use(`/${AGENT_CARD_PATH}`, agentCardHandler({ agentCardProvider: requestHandler }));
app.use(
  '/a2a/rest',
  restHandler({ requestHandler, userBuilder: UserBuilder.noAuthentication }),
);
app.use((err: unknown, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error('JANUS_A2A_UNHANDLED_ERROR', err instanceof Error ? err.name : 'UnknownError');
  res.status(500).json({ error: 'INTERNAL_SERVER_ERROR' });
});

export { app, agentCard };
export default app;
