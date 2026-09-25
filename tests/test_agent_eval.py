#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("agent_eval", ROOT/"runtime/agent_eval.py")
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def load(name):
    return json.loads((ROOT/"tests/fixtures"/name).read_text(encoding="utf-8"))

def test_pass_fixture():
    payload=load("agent_eval_pass.json")
    result=mod.audit_trace(payload)
    assert result["verdict"]=="PASS"
    assert result["score_0_100"]==100
    assert result["metrics"]["unauthorized_tool_calls"]==0
    assert result["metrics"]["unauthorized_external_effects"]==0
    assert mod.verify_result(payload,result)

def test_fail_fixture():
    payload=load("agent_eval_fail.json")
    result=mod.audit_trace(payload)
    assert result["verdict"]=="FAIL"
    codes={x["code"] for x in result["failures"]}
    assert "TOOL_NOT_ALLOWED" in codes
    assert "EXTERNAL_EFFECT_NOT_AUTHORIZED" in codes
    assert "FINAL_RECEIPT_REQUIRED" in codes
    assert "FINAL_PROVENANCE_REQUIRED" in codes
    assert result["metrics"]["loop_signals"]>=1
    assert mod.verify_result(payload,result)

if __name__=="__main__":
    test_pass_fixture()
    test_fail_fixture()
    print("JANUS_AGENT_EVAL_TESTS=PASS")
