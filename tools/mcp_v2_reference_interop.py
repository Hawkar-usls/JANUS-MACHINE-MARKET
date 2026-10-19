#!/usr/bin/env python3
"""MCP v2 official reference server dual-era stdio replay (not JANUS runtime).

Run official mcp-server-time==2026.10.19. No public endpoint, buyer
request, receipt, registry submission, or Market commerce change.
"""
import asyncio, datetime, json, os, pathlib, sys

MODERN="2026-07-28"
LEGACY="2025-11-25"
PREFIX="io.modelcontextprotocol/"
OUT=pathlib.Path(os.environ.get("JANUS_MCP_V2_REPORT","mcp-v2-interop-report.json"))

def envelope(params=None):
    p=dict(params or {})
    p["_meta"]={
        PREFIX+"protocolVersion":MODERN,
        PREFIX+"clientCapabilities":{},
        PREFIX+"clientInfo":{"name":"janus-reference-interop","version":"1.0"}}
    return p

async def exercise(era):
    p=await asyncio.create_subprocess_exec(
        "mcp-server-time",stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    n=0
    checks=[]
    async def rpc(method,params=None):
        nonlocal n
        n+=1
        data={"jsonrpc":"2.0","id":n,"method":method}
        if params is not None:data["params"]=params
        p.stdin.write((json.dumps(data,separators=(",",":"))+"\n").encode())
        await p.stdin.drain()
        raw=await asyncio.wait_for(p.stdout.readline(),timeout=24)
        if not raw:raise RuntimeError(era+" EOF on "+method)
        obj=json.loads(raw)
        if obj.get("id")!=n or obj.get("jsonrpc")!="2.0":
            raise RuntimeError(era+" JSON-RPC message ID mismatch")
        return obj
    try:
        if era==MODERN:
            d=await rpc("server/discover",envelope())
            result=d.get("result",{})
            if MODERN not in result.get("supportedVersions",[]):
                raise RuntimeError("2026 server/discover did not enumerate modern protocol")
            checks.append("MODERN_DISCOVER_PASS")
            if PREFIX+"serverInfo" not in result.get("_meta",{}):
                raise RuntimeError("modern serverInfo _meta missing")
            checks.append("MODERN_SERVER_INFO_META_PASS")
        else:
            i=await rpc("initialize",{"protocolVersion":LEGACY,
                "capabilities":{},"clientInfo":{"name":"janus-legacy-interop","version":"1.0"}})
            if i.get("result",{}).get("protocolVersion")!=LEGACY:
                raise RuntimeError("legacy initialization negotiation failed")
            p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            await p.stdin.drain()
            checks.append("LEGACY_INITIALIZE_PASS")
        params=lambda v:envelope(v) if era==MODERN else v
        ls=await rpc("tools/list",params({}))
        names=sorted(v.get("name") for v in ls.get("result",{}).get("tools",[]))
        if "get_current_time" not in names:raise RuntimeError("time tool missing")
        checks.append("TOOLS_LIST_PASS")
        good=await rpc("tools/call",params({"name":"get_current_time","arguments":{"timezone":"UTC"}}))
        v=good.get("result",{})
        if good.get("error") or v.get("isError") or not v.get("content"):
            raise RuntimeError("valid time tool failed")
        checks.append("TOOLS_CALL_CONTENT_PASS")
        if not v.get("structuredContent"):
            raise RuntimeError("time tool structuredContent missing")
        checks.append("STRUCTURED_CONTENT_PASS")
        bad=await rpc("tools/call",params({"name":"janus_mcp_nonexistent_negative_control","arguments":{}}))
        error=bad.get("error") or {}
        if error.get("code")!=-32602 or "Unknown tool" not in error.get("message",""):
            raise RuntimeError("unknown tool did not return JSON-RPC -32602: "+str(bad))
        checks.append("UNKNOWN_TOOL_MINUS32602_PASS")
        return {"protocol":era,"checks":checks,"tools":names}
    finally:
        if p.returncode is None:
            p.terminate()
            try:await asyncio.wait_for(p.wait(),timeout=8)
            except asyncio.TimeoutError:p.kill();await p.wait()
        if not p.stdin.is_closing():p.stdin.close()

def market_firewall():
    load=lambda path:json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    baseline=load("discovery/MCP_2026_07_28_BASELINE.json")
    pub=load("discovery/MCP_PUBLICATION.json")
    commerce=load("COMMERCE_READINESS.json")
    pricing=load("PRICING.json")
    witness=load("FOREIGN_AGENT_WITNESS.json")
    assert baseline["spec_revision"]==MODERN
    assert baseline["janus_publication_policy"]["live_mcp_server_exists"] is False
    assert pub["current_publication_allowed"] is False
    assert pub["server_card_publication_allowed"] is False
    assert pub["ai_catalog_mcp_entry_publication_allowed"] is False
    assert not pathlib.Path("server.json").exists()
    assert witness["foreign_agent_witness"] is False
    assert witness["promotion_authority"]=="PERSISTENT_HOME_RECEIPT_ONLY"
    assert commerce["seller_commerce_authorized"] is True
    assert commerce["money_enabled"] is True
    assert "JANUS.SEARCH" in pricing["live_skus"]
    assert commerce["required_live_gates"]["first_real_paid_delivery"]=="PENDING"
    return ["NO_LIVE_MARKET_MCP_SERVER_CLAIM","MCP_PUBLICATION_STILL_BLOCKED",
            "FOREIGN_AGENT_WITNESS_UNCHANGED_FALSE",
            "PAID_JANUS_SEARCH_COMMERCE_UNCHANGED",
            "FIRST_REAL_PAID_DELIVERY_STILL_PENDING"]

async def main():
    firewall=market_firewall()
    cases=[await exercise(MODERN),await exercise(LEGACY)]
    obj={
      "schema":"janus.machine_market.mcp_v2_reference_interop.v1",
      "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "reference_release":"https://github.com/modelcontextprotocol/servers/releases/tag/v2.0.0",
      "package":"mcp-server-time==2026.10.19",
      "scope":"REAL_OFFICIAL_REFERENCE_SERVER_STDIO__NOT_MARKET_MCP_RUNTIME",
      "results":cases,"market_firewall":firewall,
      "outcome":"UPSTREAM_MODERN_LEGACY_INTEROP_PASS_ONLY",
      "market_mcp_published":False,"foreign_agent_witness":False,
      "paid_delivery_observed":False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print("JANUS_MCP_V2_REFERENCE_REPORT",str(OUT),flush=True)
    print(json.dumps({"outcome":obj["outcome"],"results":cases,"firewall":firewall}))
if __name__=="__main__":
    try:asyncio.run(main())
    except Exception as e:
        print("MCP_V2_REFERENCE_FAIL "+type(e).__name__+": "+str(e),file=sys.stderr,flush=True)
        raise
