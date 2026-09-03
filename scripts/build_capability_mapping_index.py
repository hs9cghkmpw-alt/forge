"""Capability ID から、候補となる Source / Test / Evidence / TD を抽出する。

**候補抽出まで**が仕事である。最終 Status は意味を見て人が決める
（CEO 指示 §4「単純Keyword一致だけで状態を自動決定しない」）。
"""
import json, pathlib, re, subprocess, sys

ROOT = pathlib.Path('/home/user/forge')

# Capability ごとの検索語。**能力の意味**から引いた語であり、ID 文字列ではない。
TERMS = {
 "AI-01": ["intent_parser","semantic","need_model","natural_language"],
 "AI-02": ["conversation_fast_path","ASK","BUILD","readiness"],
 "AI-03": ["question_strategy","blocking_unknown","open_question"],
 "AI-04": ["correction","hypothesis","stateful"],
 "AI-05": ["capability_plan","decompos","goal","constraint"],
 "AI-06": ["capability_gap","unknown_capability","tier"],
 "AI-07": ["conversation_store","session","turn","long_context"],
 "AI-08": ["wrong_meaning","semantic_design","must_mean","required_semantics"],
 "AI-09": ["ai_router","routing","ForgeTask","bind("],
 "AI-10": ["benchmark","blind","provider_comparison","a_b"],
 "GEN-01": ["converse","ConversationBuilt","end_to_end","e2e"],
 "GEN-02": ["forge_ir","forge_language","ir_builder"],
 "GEN-03": ["schema_validator","validate_forge_document"],
 "GEN-04": ["validator","mutation"],
 "GEN-05": ["repair","forge_operation","attempts"],
 "GEN-06": ["widget_registry","forge_renderer","json_ui"],
 "GEN-07": ["crud","record_list_view","persistence","form"],
 "GEN-08": ["workflow","approval","inventory","reservation"],
 "GEN-09": ["special_ui","encoding","view.map","map_view"],
 "GEN-10": ["game","simulation_loop","collision","rule"],
 "GEN-11": ["drag","animation","realtime","gesture"],
 "GEN-12": ["screen","navigation","route","back_stack","tab_view"],
 "GEN-13": ["external_service","tool_broker","permission_broker","web"],
 "GEN-14": ["web","fetch_url","injection_scan","untrusted"],
 "EXT-01": ["capability_gap","missing_capability","gap_detect"],
 "EXT-02": ["capability_decomposition","semantic_capability"],
 "EXT-03": ["extension_manifest","contract","permission"],
 "EXT-04": ["capability_artifact_synthesis","synthesizing_build_time"],
 "EXT-05": ["runtime_attested_widgets","validator_binding"],
 "EXT-06": ["flutter_capability_installer","acquired"],
 "EXT-07": ["capability_test.dart","dart run","generated test"],
 "EXT-08": ["sandbox","isolat","seccomp","unshare"],
 "EXT-09": ["safety_review","p0","p1","danger"],
 "EXT-10": ["promotion","PROMOTED","extension_registry"],
 "EXT-11": ["reuse_first","PROMOTED_CAPABILITIES","reuse"],
 "EXT-12": ["improve","non_regression","capability_version"],
 "EXT-13": ["retire","removal","migration","rollback"],
 "EXT-14": ["self_extension_loop","extension_cycle"],
 "LOC-01": ["local_provider","ollama","FORGE_LOCAL"],
 "LOC-02": ["model_choice","quantization","model_profile"],
 "LOC-03": ["local_model_evidence","local_promotion"],
 "LOC-04": ["warm","cache","preload"],
 "LOC-05": ["offline"],
 "LOC-06": ["peak_rss","memory","resource"],
 "LOC-07": ["gpu","cpu","device_profile"],
 "LOC-08": ["execution_resolver","host","delegat"],
 "LOC-09": ["privacy","local_first"],
 "LOC-10": ["low_resource","profile"],
 "LOC-11": ["model_digest","model_swap"],
 "LRN-01": ["experience","ExperienceStore","episode"],
 "LRN-02": ["dataset","training"],
 "LRN-03": ["teacher","distill"],
 "LRN-04": ["benchmark","novel_benchmark"],
 "LRN-05": ["evaluator","critic","design_critic"],
 "LRN-06": ["gym","episode"],
 "LRN-07": ["knowledge","rag","retrieval"],
 "LRN-08": ["acceptance_signal","feedback"],
 "LRN-09": ["promotion_rule","promote"],
 "LRN-10": ["provenance","lineage"],
 "LRN-11": ["skill"],
 "LRN-12": ["curriculum"],
 "LRN-13": ["regression","non_regression"],
 "UI-01": ["design_language","theme","forge_theme"],
 "UI-02": ["design_critic","visual"],
 "UI-03": ["responsive","ResponsiveAppShell"],
 "UI-04": ["accessibility","Semantics","Tooltip"],
 "UI-05": ["contrast","color"],
 "UI-06": ["typography","font"],
 "UI-07": ["layout","overflow"],
 "UI-08": ["empty_state","error_state"],
 "UI-09": ["loading","progress","thinking"],
 "UI-10": ["information_architecture","section_header"],
 "UI-11": ["ai_mode","provider_independent"],
 "UI-12": ["voice","speech_to_text"],
 "UI-13": ["navigation","history","my_apps"],
 "UI-14": ["golden","visual_evidence","screenshot"],
 "QA-01": ["pytest","flutter test","unit"],
 "QA-02": ["integration","e2e"],
 "QA-03": ["mutation","guard_break","配線破壊"],
 "QA-04": ["ci",".github/workflows"],
 "QA-05": ["model_call_ledger","attribution","evidence_integrity"],
 "QA-06": ["coverage"],
 "QA-07": ["soak","stress"],
 "QA-08": ["flaky","determinism"],
 "QA-09": ["golden_conversation"],
 "QA-10": ["quality_gate"],
 "QA-11": ["regression_suite"],
 "QA-12": ["release_gate","freeze"],
 "SEC-01": ["injection_scan","prompt_injection"],
 "SEC-02": ["output_safety","safety_checker"],
 "SEC-03": ["permission_broker","permission"],
 "SEC-04": ["tool_broker","bounded_tool"],
 "SEC-05": ["secret","api_key","redact"],
 "SEC-06": ["external_call_policy","default_deny"],
 "SEC-07": ["supply_chain","dependency","allowlist"],
 "SEC-08": ["sandbox","escape"],
 "SEC-09": ["audit","provenance"],
 "SEC-10": ["threat_model"],
 "PRD-01": ["distribution","installer","self_contained"],
 "PRD-02": ["onboarding","first_run"],
 "PRD-03": ["saved_app","app_library","persistence"],
 "PRD-04": ["update","migration"],
 "PRD-05": ["backup","recovery"],
 "PRD-06": ["sync"],
 "PRD-07": ["multi_device","cross_device"],
 "PRD-08": ["offline"],
 "PRD-09": ["error_message","friendly"],
 "PRD-10": ["settings","config"],
 "PRD-11": ["export","share"],
 "PRD-12": ["licence","license"],
 "PRD-13": ["telemetry","metrics"],
 "PRD-14": ["support","docs"],
 "PRD-15": ["release","version"],
 "PER-01": ["latency","p95","timing","stage_timing"],
 "PER-02": ["throughput"],
 "PER-03": ["startup","boot"],
 "PER-04": ["memory","rss"],
 "PER-05": ["scale","large"],
 "PER-06": ["cache"],
 "PER-07": ["concurrency","parallel"],
 "PER-08": ["battery","power"],
}

SEARCH_ROOTS = ["backend/app", "forge_ai", "frontend/lib", "scripts"]
TEST_ROOTS = ["backend/tests", "forge_ai/tests", "frontend/test", "frontend/test_acquired"]
EVIDENCE_ROOTS = ["docs/evidence", "docs/reports", "docs/architecture", "docs/adr"]

def rg(term, roots):
    try:
        out = subprocess.run(
            ["rg","-l","--no-messages","-i","-F",term,*[str(ROOT/r) for r in roots if (ROOT/r).exists()]],
            capture_output=True, text=True, timeout=60)
        return [p.replace(str(ROOT)+"/","") for p in out.stdout.strip().split("\n") if p]
    except Exception:
        return []

def td_hits(term):
    td = (ROOT/"TECH_DEBT.md").read_text(encoding="utf-8")
    return sorted({m.group(0) for m in re.finditer(r"TD\d+", 
            "\n".join(l for l in td.split("\n") if term.lower() in l.lower()))})

index = {}
for cid, terms in TERMS.items():
    src, tst, ev, tds = set(), set(), set(), set()
    for t in terms:
        src.update(rg(t, SEARCH_ROOTS)[:12])
        tst.update(rg(t, TEST_ROOTS)[:12])
        ev.update(rg(t, EVIDENCE_ROOTS)[:8])
        tds.update(td_hits(t))
    index[cid] = {
        "search_terms": terms,
        "source_candidates": sorted(src)[:12],
        "test_candidates": sorted(tst)[:12],
        "evidence_candidates": sorted(ev)[:8],
        "tech_debt_candidates": sorted(tds)[:8],
    }
    print(f"{cid}: src={len(src)} test={len(tst)} ev={len(ev)} td={len(tds)}", file=sys.stderr)

out = ROOT/"docs/evidence/capability_matrix/mapping_index.json"
out.write_text(json.dumps({
  "schema_version":"1.0","generated_at":"2026-09-04",
  "purpose":"Capability ID から Source/Test/Evidence/TD の**候補**を引く索引。候補抽出までが仕事であり、最終Statusは意味を確認して人が決める。",
  "generator":"scripts/build_capability_mapping_index.py",
  "capabilities": index,
}, ensure_ascii=False, indent=1)+"\n", encoding="utf-8")
print("WROTE", out, file=sys.stderr)
