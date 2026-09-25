# JANUS Market Telegram + Machine Gateway

Status: **prepared, not live**.

The existing ChatGPT Site supplied by the owner is intended to become a convenience frontend:

`https://tg-pomoyka.hawkarlol.chatgpt.site`

The site is not an execution authority. The safe architecture is:

```text
ChatGPT Site / Telegram / machine client
        ↓
JANUS Gateway
  - identity normalization
  - webhook/HMAC authentication
  - nonce + idempotency ledger
  - one-first-free entitlement ledger
  - rate / concurrency / hop limits
        ↓
GitHub App (Market issues:write only)
        ↓
JANUS-MACHINE-MARKET admission
        ↓
credentialless HOME pull
        ↓
persistent JANUS
        ↓
Market reconcile
        ↓
signed result callback
        ↓
Telegram / machine client
```

## Human Telegram orders

Order creation defaults to **private chats only**.

The gateway derives the principal from the immutable Telegram numeric sender id:

`telegram:user:<id>`

Usernames are presentation metadata and are not authority.

The first new `JANUS.SEARCH` order for a principal is free. A later new order is not free. An exact retry of the same idempotency key returns the prior receipt and does not create a second cognition or consume another entitlement.

## Machine clients

Machines should prefer the HTTPS machine endpoint rather than impersonating a human Telegram account.

Each machine receives a key id and secret. Requests bind:

```text
key_id
timestamp
nonce
hop_count
SHA256(body)
```

with HMAC-SHA256. The default clock window is 300 seconds, nonce reuse is rejected, an idempotency key is mandatory, and hop count is limited to one.

Telegram now supports bot-to-bot communication when Bot-to-Bot Communication Mode is enabled, but JANUS still treats it as an optional transport, not as identity or execution authority. A bot-generated message alone does not satisfy the FOREIGN_AGENT_WITNESS gate.

## Telegram webhook

Use Telegram `setWebhook` with a `secret_token`. Every accepted update must carry the matching:

`X-Telegram-Bot-Api-Secret-Token`

header.

Only `message` and `callback_query` update types should be enabled for the first deployment. Edited messages do not alter an admitted order.

## Abuse protection

Activation requires a durable store. In-memory/serverless-local-only state is insufficient.

The durable ledger must record at least:

- processed Telegram `update_id`;
- machine nonce;
- idempotency key -> immutable Market receipt;
- canonical principal and explicitly linked aliases;
- whether the principal already consumed the first free SEARCH;
- currently active order for the principal;
- last admitted order timestamp;
- block/abuse state.

Frozen initial limits:

- one active order per principal;
- 30 second new-order cooldown;
- one first free SEARCH per external principal;
- 20 first-free SEARCH admissions globally per UTC day;
- 4 KiB SEARCH input;
- 6 KiB bounded answer;
- machine / bot-to-bot hop depth <= 1;
- unknown SKU denied;
- arbitrary shell, repository write, secret access and external effects denied.

## Cross-platform identity

Do **not** guess that a Telegram account, GitHub account and machine API key belong to the same person.

They share one free entitlement only after an explicit account-link operation binds their principal aliases. Until then they are independent principals.

## Specialist organs

The Market catalog may advertise TOPA, Demiurge, Cousteau and other JANUS organs for discovery. They are not public executable services merely because they appear in the catalog.

See `ORGAN_SERVICE_MATRIX.json`. A specialist SKU becomes live only after its dedicated:

`Market -> HOME -> organ -> HOME -> Market`

receipt is demonstrated end-to-end.

## Results back to Telegram

The Market reconcile path should call a separate gateway result endpoint authenticated with a dedicated callback HMAC secret. GitHub does not receive the Telegram bot token.

The gateway verifies the order id / principal binding, then sends the bounded result plus receipt id to the original chat.

## Required secrets

Never commit:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- machine HMAC keys
- result callback secret
- GitHub App private key / installation credentials

The preferred GitHub identity is a dedicated GitHub App installed only on `JANUS-MACHINE-MARKET` with the minimum permissions needed for issue creation.

## ChatGPT Site binding

The current chat cannot directly edit the owner's ChatGPT Site or its private environment. Therefore the Site binding remains pending until the site is edited to call the deployed gateway (or link/open the Telegram bot).

No secret may be embedded in public browser JavaScript. If the Site cannot hold server-side secrets/actions, keep it as a public UI and send privileged requests only through the external gateway.

## Activation receipt

Do not mark Telegram ingress live until all of these pass:

1. HTTPS gateway deployed.
2. Telegram webhook secret verified.
3. Durable anti-replay/entitlement ledger verified.
4. Bot token server-side only.
5. Scoped GitHub issue writer verified.
6. Telegram message -> Market issue -> HOME -> result -> same Telegram principal replay passes.
7. Duplicate webhook produces the same receipt and zero new execution.
8. Second free SEARCH from the same principal is denied.
9. Bot-to-bot loop negative control passes if that mode is enabled.

