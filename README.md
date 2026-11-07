# Stanza Agent v3.2 — Sovereign Intelligent Document & Structural Engine for ARA OS 12

[![CI/CD Pipeline](https://github.com/allyxzs/stanza-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/allyxzs/stanza-agent/actions)
[![Python 3.10 | 3.11 | 3.12](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![ARA OS 12](https://img.shields.io/badge/ARA%20OS-12.4%20Sovereign-purple)](https://github.com/allyxzs/stanza-agent)
[![Security](https://img.shields.io/badge/Security-Zero--Trust%20%2B%20HMAC--SHA256-success)](https://github.com/allyxzs/stanza-agent)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Stanza Agent v3.2** is the Intelligent Document, Linguistic, and Structural Autonomous Agent engineered for **ARA OS 12**. It unifies deep hierarchical document intelligence, semantic "Stanza" segmentation, Python AST static verification, 3-tier hybrid cognitive memory, self-healing topological DAG orchestration, and immutable HMAC-SHA256 + Merkle Tree cryptographic provenance.

---

## Architectural Blueprint (v3.2 Sovereign Upgrade)

```mermaid
graph TD
    User([Document / Mission Directive / Code]) --> Shield[Zero-Trust Prompt Firewall<br/>Regex Heuristics + Shannon Entropy]
    Shield -- Blocked --> AuditReject[Cryptographic Ledger<br/>Record Threat Vector]
    Shield -- Verified Safe --> DAG[Self-Healing Topological DAG Orchestrator]

    subgraph Parallel Execution Layer 1
        DAG --> Doc[ARA OS 12 Document Intelligence<br/>Section Hierarchy + Flesch Readability + SHA256]
        DAG --> NLP[Stanza Linguistic Engine<br/>Semantic Segmentation + NER + Intent]
        DAG --> Mem[Hybrid Cognitive Memory<br/>SQLite 3-Tier: BM25 + Cosine + Decay]
        DAG --> AST[Structural AST Verifier<br/>Cyclomatic Complexity + Sandbox Escapes]
    end

    Doc --> Synth[Neuro-Symbolic Synthesizer<br/>Contextual Grounding + Episodic Storage]
    NLP --> Synth
    Mem --> Synth
    AST --> Synth

    Synth --> Ledger[Immutable Cryptographic Ledger<br/>HMAC-SHA256 Signatures + Merkle Root]
    Ledger --> Output([Verified Mission Response + Cryptographic Proof])
```

---

## Core Subsystems & v3.2 Improvements

| Subsystem | Module | Key Capabilities |
| :--- | :--- | :--- |
| **ARA OS 12 Document Engine** | `src/stanza/document/ara_engine.py` | Hierarchical Markdown/Document section parser, Flesch-Kincaid readability scoring, key-term TF extraction, and SHA-256 section fingerprinting. |
| **Zero-Trust Shield** | `src/stanza/security/shield.py` | Multi-vector regex heuristics (System Override, Role Hijack, Command/SQL Injection, Python Sandbox Escape) + Shannon Entropy obfuscation detector. |
| **Cryptographic Ledger** | `src/stanza/security/audit.py` | Immutable hash-chained audit trail with **HMAC-SHA256** signatures and dynamic **Merkle Tree Root** recalculation on every state transition. |
| **Stanza Linguistic Engine** | `src/stanza/nlp/engine.py` | Decomposes unstructured text into semantic *Stanzas*, computes syntactic density & lexical complexity, extracts entities (IPv4, CVE, Hashes, Paths), and inspects Python AST trees. |
| **Hybrid Cognitive Memory** | `src/stanza/memory/cognitive_store.py` | Persistent SQLite 3-Tier store (`EPISODIC`, `SEMANTIC`, `PROCEDURAL`) combining **Okapi BM25**, **Cosine Vector Similarity**, and **Exponential Temporal Decay**. |
| **Self-Healing DAG Engine** | `src/stanza/core/dag.py` | Topological sort dependency resolution with cycle detection, concurrent layer execution (`asyncio.gather`), retry backoff, and autonomous fallback healing daemons. |

---

## Quickstart & Verification

```bash
# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Verify subsystem matrix via CLI
stanza info

# Execute an autonomous document & code mission
stanza run "# Kernel Audit
Verify CVE-2026-4410 on 10.0.0.15." --code "import hashlib
def h(x): return hashlib.sha256(x).hexdigest()"

# Run Ruff linter & Pytest suite
ruff check src/ tests/
pytest -v
```

---

## License

Engineered by **allyxzs**. Released under the [MIT License](LICENSE).
