from typing import Dict, Any, Optional, List
from dataclasses import asdict
from stanza.config.settings import settings
from stanza.security.shield import PromptFirewall
from stanza.security.audit import CryptographicLedger
from stanza.nlp.engine import StanzaLinguisticEngine
from stanza.memory.cognitive_store import HybridCognitiveMemory
from stanza.core.dag import SelfHealingDAGOrchestrator, DAGTaskNode


class StanzaAutonomousAgent:
    """
    Master Stanza v3.0 Multi-Agent Coordinator.
    Unifies Zero-Trust Security, Linguistic Stanza Segmentation, Hybrid Cognitive Memory,
    Self-Healing DAG Execution, and Cryptographic Provenance Auditing.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        ledger_path: Optional[str] = None,
        strict_security: bool = True,
    ):
        self.firewall = PromptFirewall(strict_mode=strict_security)
        self.ledger = CryptographicLedger(
            secret_key=settings.hmac_secret_key,
            storage_path=ledger_path,
        )
        self.nlp = StanzaLinguisticEngine()
        self.memory = HybridCognitiveMemory(db_path=db_path or ":memory:")
        self._seed_procedural_knowledge()

    def _seed_procedural_knowledge(self) -> None:
        if self.memory.stats()["total_records"] == 0:
            self.memory.store(
                content="Stanza Protocol v3: Decompose complex prompts into atomic linguistic stanzas before DAG synthesis.",
                tier="PROCEDURAL",
                tags=["protocol", "stanza", "dag"],
                importance=0.95,
            )
            self.memory.store(
                content="Zero-Trust Directive: All code synthesis outputs must pass Python AST structural and security inspection.",
                tier="PROCEDURAL",
                tags=["security", "ast", "verification"],
                importance=0.98,
            )
            self.memory.store(
                content="Audit Mandate: Every reasoning pipeline stage must be signed with HMAC-SHA256 and chained into the Merkle Ledger.",
                tier="SEMANTIC",
                tags=["cryptography", "merkle", "audit"],
                importance=0.92,
            )

    async def _default_healer(self, node_id: str, exc: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
        self.ledger.record_event(
            actor="SELF_HEALING_DAEMON",
            action=f"RECOVER_NODE_{node_id}",
            payload={"error": str(exc)},
        )
        return {"healed": True, "recovered_node": node_id, "fallback_reason": str(exc)}

    async def process_mission(self, prompt: str, code_snippet: Optional[str] = None) -> Dict[str, Any]:
        # 1. Pre-Flight Zero-Trust Security Gate
        verdict = self.firewall.inspect(prompt)
        self.ledger.record_event(
            actor="ZERO_TRUST_SHIELD",
            action="INSPECT_PROMPT",
            payload={"is_safe": verdict.is_safe, "threat_score": verdict.threat_score, "vectors": verdict.detected_vectors},
        )

        if not verdict.is_safe:
            return {
                "status": "BLOCKED_BY_FIREWALL",
                "security_verdict": asdict(verdict),
                "audit_integrity": self.ledger.verify_integrity(),
            }

        # 2. Build Multi-Stage DAG Pipeline
        dag = SelfHealingDAGOrchestrator(fallback_healer=self._default_healer)

        async def node_linguistic_parse(ctx: Dict[str, Any]) -> Dict[str, Any]:
            stanzas = self.nlp.segment_into_stanzas(ctx["raw_prompt"])
            primary_intent = stanzas[0].intent_category if stanzas else "GENERAL_REASONING"
            return {
                "stanza_count": len(stanzas),
                "primary_intent": primary_intent,
                "stanzas": [asdict(s) for s in stanzas],
            }

        async def node_memory_retrieval(ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
            recalled = self.memory.retrieve(ctx["raw_prompt"], top_k=3)
            return [asdict(r) for r in recalled]

        async def node_ast_verification(ctx: Dict[str, Any]) -> Dict[str, Any]:
            snippet = ctx.get("code_snippet")
            if not snippet:
                return {"inspected": False, "status": "NO_CODE_PROVIDED"}
            analysis = self.nlp.analyze_python_ast(snippet)
            return asdict(analysis)

        async def node_cognitive_synthesis(ctx: Dict[str, Any]) -> Dict[str, Any]:
            parse_data = ctx["linguistic_stanza_parser"]
            memories = ctx["cognitive_memory_retriever"]
            ast_data = ctx["structural_ast_verifier"]

            # Persist episodic memory of this mission
            mem_id = self.memory.store(
                content=f"Mission executed with intent {parse_data['primary_intent']}: {ctx['raw_prompt'][:120]}",
                tier="EPISODIC",
                tags=[parse_data["primary_intent"].lower(), "mission"],
                importance=0.80,
            )

            synthesis_summary = (
                f"Processed {parse_data['stanza_count']} stanza(s) under primary intent "
                f"'{parse_data['primary_intent']}'. Grounded with {len(memories)} cognitive memory trace(s)."
            )
            return {
                "summary": synthesis_summary,
                "episodic_memory_id": mem_id,
                "primary_intent": parse_data["primary_intent"],
                "ast_valid": ast_data.get("is_valid_python", True),
            }

        dag.add_node(DAGTaskNode("linguistic_stanza_parser", "Segment prompt into semantic stanzas", node_linguistic_parse))
        dag.add_node(DAGTaskNode("cognitive_memory_retriever", "Retrieve hybrid BM25+Vector memories", node_memory_retrieval))
        dag.add_node(DAGTaskNode("structural_ast_verifier", "Inspect code AST structure & safety", node_ast_verification))
        dag.add_node(
            DAGTaskNode(
                "neuro_symbolic_synthesizer",
                "Synthesize final verified response",
                node_cognitive_synthesis,
                dependencies=["linguistic_stanza_parser", "cognitive_memory_retriever", "structural_ast_verifier"],
            )
        )

        dag_output = await dag.execute({"raw_prompt": prompt, "code_snippet": code_snippet})

        # 3. Record Cryptographic Provenance Block
        latest_block = self.ledger.record_event(
            actor="STANZA_ORCHESTRATOR",
            action="MISSION_COMPLETED",
            payload={
                "intent": dag_output["context"]["neuro_symbolic_synthesizer"]["primary_intent"],
                "stanza_count": dag_output["context"]["linguistic_stanza_parser"]["stanza_count"],
                "telemetry": dag_output["telemetry"],
            },
        )

        return {
            "status": "SUCCESS",
            "security_verdict": asdict(verdict),
            "linguistic_analysis": dag_output["context"]["linguistic_stanza_parser"],
            "recalled_memories": dag_output["context"]["cognitive_memory_retriever"],
            "ast_analysis": dag_output["context"]["structural_ast_verifier"],
            "synthesis": dag_output["context"]["neuro_symbolic_synthesizer"],
            "dag_telemetry": dag_output["telemetry"],
            "cryptographic_proof": asdict(latest_block),
            "audit_integrity": self.ledger.verify_integrity(),
        }
