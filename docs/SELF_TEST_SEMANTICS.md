# JANUS Machine Market Self-Test Semantics

The Market self-test has two deliberately separate identities.

1. `internal-test:chatgpt-gpt-5.6-sol` is a synthetic integration-test buyer. It may receive `MARKET_TEST_CREDIT`, which has no cash value and is never payment proof. It exists to exercise account, balance, replay, pricing and admission contracts.
2. A live GitHub owner-shadow request exercises the already-canonical public Market → credentialless HOME → Activator → persistent JANUS → HRAiN → RETURN HOME → Market transport. It is a real runtime witness but is not a foreign-buyer witness and uses no money.

A service is reported as operational only when a real result receipt exists. `SPECIFICATION_READY` is not treated as fulfillment. `JANUS.INFERENCE` and `JANUS.COMPUTE` must fail closed until their target-execution witness is admitted. `HELIOS.PILOT` is excluded from this test campaign and must not be invoked.
