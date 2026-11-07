import os
from pydantic import BaseModel, Field


class StanzaSettings(BaseModel):
    app_name: str = "Stanza Agent v3.2 (ARA OS 12)"
    version: str = "3.2.0"
    ara_os_kernel_version: str = "ARA-OS-12.4-SOVEREIGN"
    environment: str = Field(default_factory=lambda: os.getenv("STANZA_ENV", "development"))
    db_path: str = Field(default_factory=lambda: os.getenv("STANZA_DB_PATH", "stanza_cognitive.db"))
    ledger_path: str = Field(default_factory=lambda: os.getenv("STANZA_LEDGER_PATH", "stanza_audit_ledger.json"))
    max_dag_concurrency: int = 8
    max_healing_retries: int = 3
    zero_trust_strict_mode: bool = True
    hmac_secret_key: str = Field(
        default_factory=lambda: os.getenv("STANZA_HMAC_SECRET", "stanza-v3-2-sovereign-cryptographic-key-99481")
    )
    bm25_k1: float = 1.5
    bm25_b: float = 0.75


settings = StanzaSettings()
