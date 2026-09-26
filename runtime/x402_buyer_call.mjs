import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { CdpX402Client, SpendControlError } from "@coinbase/cdp-sdk/x402";
import { wrapFetchWithPayment } from "@x402/fetch";

const POLICY_PATH = process.env.JANUS_X402_POLICY ?? "X402_BUYER_POLICY.json";
const CONFIRM_PHRASE = "PAY_0_005_USDC_TO_MACH";
const USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913";

function sha256(value) {
  return createHash("sha256").update(value ?? "", "utf8").digest("hex");
}

function fail(message) {
  throw new Error(message);
}

function loadPolicy() {
  return JSON.parse(readFileSync(POLICY_PATH, "utf8"));
}

function validatePolicy(policy, target) {
  if (policy?.status !== "OWNER_AUTHORIZED_BOUNDED_BUYER_PILOT_ENABLED") {
    fail(`buyer pilot is not enabled: ${policy?.status ?? "missing"}`);
  }
  if (policy?.separation_law?.external_buyer_spend_enabled !== true) fail("external buyer spend disabled");
  if (policy?.separation_law?.seller_money_enabled !== false) fail("seller money boundary must remain false");
  if (policy?.foreign_agent_witness?.expected_during_this_pilot !== false) fail("foreign witness boundary drift");

  const url = new URL(target);
  const p = policy.pilot;
  if (target !== p.resource) fail("target must exactly match frozen pilot resource");
  if (url.protocol !== "https:") fail("HTTPS required");
  if (!p.allowed_hosts.includes(url.hostname)) fail("host not allowlisted");
  if (!p.allowed_paths.includes(url.pathname)) fail("path not allowlisted");
  if (!p.allowed_methods.includes("GET")) fail("GET not allowlisted");
  if (p.network !== "eip155:8453") fail("only Base mainnet is allowed");
  if (String(p.asset.contract).toLowerCase() !== USDC_BASE) fail("unexpected Base USDC contract");
  if (Number(p.max_atomic_per_payment) !== 5000) fail("pilot cap must remain exactly 5000 atomic USDC");
  if (Number(p.max_atomic_per_24h) !== 5000) fail("24h pilot cap must remain exactly 5000 atomic USDC");
}

async function main() {
  const policy = loadPolicy();
  const target = process.env.JANUS_X402_TARGET ?? policy.pilot.resource;
  const confirm = process.env.JANUS_X402_OPERATOR_CONFIRM ?? "";
  if (confirm !== CONFIRM_PHRASE) fail(`operator confirmation must equal ${CONFIRM_PHRASE}`);
  validatePolicy(policy, target);

  for (const key of policy.signer.required_environment_secrets) {
    if (!process.env[key]) fail(`missing required signer secret: ${key}`);
  }

  const outputPath = process.env.JANUS_X402_RECEIPT ?? "artifacts/x402-buyer/latest.json";
  mkdirSync(dirname(resolve(outputPath)), { recursive: true });

  const client = new CdpX402Client({
    environment: "production",
    spendControls: {
      maxAmountPerPayment: { atomic: 5000n, asset: USDC_BASE },
      maxCumulativeSpend: { atomic: 5000n, asset: USDC_BASE },
      maxCumulativeSpendWindow: "24h",
      allowedNetworks: ["eip155:8453"],
      allowedAssets: [USDC_BASE],
    },
  });

  const { evmAddress } = await client.getAddresses();
  const startedAt = new Date().toISOString();
  const paidFetch = wrapFetchWithPayment(globalThis.fetch, client);

  let response;
  let body = "";
  let error = null;
  try {
    response = await paidFetch(target, {
      method: "GET",
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(30_000),
    });
    body = await response.text();
  } catch (err) {
    error = err instanceof Error ? `${err.name}: ${err.message}` : String(err);
  }

  const paymentResponse = response?.headers?.get("payment-response") ?? response?.headers?.get("x-payment-response") ?? "";
  const receipt = {
    schema: policy.receipt.schema,
    recorded_at: new Date().toISOString(),
    started_at: startedAt,
    provider: policy.pilot.provider,
    provider_principal: policy.pilot.provider_principal,
    resource: target,
    method: "GET",
    payer_address: evmAddress,
    network: policy.pilot.network,
    asset: policy.pilot.asset,
    max_atomic_authorized: policy.pilot.max_atomic_per_payment,
    http_status: response?.status ?? null,
    response_sha256: sha256(body),
    response_body_preview: body.slice(0, 1000),
    payment_response_header_sha256: sha256(paymentResponse),
    payment_response_header_present: paymentResponse.length > 0,
    owner_authorized_buyer_test: true,
    foreign_agent_witness: false,
    seller_money_enabled: false,
    ambiguous_outcome_retry_allowed: false,
    error,
  };
  writeFileSync(outputPath, `${JSON.stringify(receipt, null, 2)}\n`, "utf8");

  console.log(`JANUS_X402_BUYER_RECEIPT=${outputPath}`);
  console.log(`JANUS_X402_PAYER=${evmAddress}`);
  console.log(`JANUS_X402_HTTP_STATUS=${receipt.http_status}`);
  console.log(`JANUS_X402_RESPONSE_SHA256=${receipt.response_sha256}`);
  console.log(`JANUS_X402_PAYMENT_RESPONSE_PRESENT=${receipt.payment_response_header_present}`);

  if (error) fail(`x402 call failed after authorization; DO NOT RETRY AUTOMATICALLY: ${error}`);
  if (!response?.ok) fail(`x402 resource returned HTTP ${response?.status}; DO NOT RETRY AUTOMATICALLY`);
}

main().catch((err) => {
  if (err instanceof SpendControlError) {
    console.error(`JANUS_X402_SPEND_CONTROL_BLOCK=${err.code ?? "UNKNOWN"}: ${err.message}`);
  } else {
    console.error(err);
  }
  process.exit(1);
});
