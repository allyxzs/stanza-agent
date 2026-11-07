from dataclasses import asdict
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from stanza.config.settings import settings
from stanza.core.orchestrator import StanzaAutonomousAgent

app = FastAPI(
    title="Stanza Agent v3.2 Sovereign API (ARA OS 12)",
    description="Intelligent Document, Linguistic, Structural & Semantic Reasoning Engine with Cryptographic Provenance",
    version=settings.version,
)

agent = StanzaAutonomousAgent(
    db_path=settings.db_path,
    ledger_path=settings.ledger_path,
    strict_security=settings.zero_trust_strict_mode,
)


class MissionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Mission directive or document text to analyze")
    code_snippet: Optional[str] = Field(None, description="Optional Python source code for AST structural verification")


class DocumentAnalysisRequest(BaseModel):
    document: str = Field(..., min_length=1, description="Raw Markdown or structured text document for ARA OS 12 analysis")


class MemoryCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    tier: str = Field("SEMANTIC", description="EPISODIC, SEMANTIC, or PROCEDURAL")
    tags: List[str] = Field(default_factory=list)
    importance: float = Field(0.8, ge=0.0, le=1.0)


@app.get("/health")
async def health_check():
    integrity = agent.ledger.verify_integrity()
    return {
        "status": "ONLINE",
        "agent": settings.app_name,
        "version": settings.version,
        "ara_os_kernel": settings.ara_os_kernel_version,
        "ledger_integrity": integrity,
        "memory_stats": agent.memory.stats(),
    }


@app.post("/v1/mission")
async def execute_mission(request: MissionRequest):
    result = await agent.process_mission(prompt=request.prompt, code_snippet=request.code_snippet)
    if result["status"] == "BLOCKED_BY_FIREWALL":
        raise HTTPException(status_code=403, detail=result)
    return result


@app.post("/v1/document/analyze")
async def analyze_document_endpoint(request: DocumentAnalysisRequest):
    report = agent.doc_engine.analyze_document(request.document)
    return asdict(report)


@app.post("/v1/memory")
async def store_memory(request: MemoryCreateRequest):
    record_id = agent.memory.store(
        content=request.content,
        tier=request.tier,
        tags=request.tags,
        importance=request.importance,
    )
    return {"status": "STORED", "record_id": record_id, "stats": agent.memory.stats()}


@app.get("/v1/audit/verify")
async def verify_audit_chain():
    return agent.ledger.verify_integrity()
