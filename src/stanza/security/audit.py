from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, List, Optional


@dataclass
class AuditBlock:
    index: int
    timestamp: float
    actor: str
    action: str
    payload_hash: str
    previous_hash: str
    merkle_root: str
    signature: str
    block_hash: str


class CryptographicLedger:
    """
    Immutable Hash-Chained Audit Ledger with HMAC-SHA256 & Merkle Root Verification.
    Ensures every Stanza Agent reasoning step is cryptographically verifiable.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, secret_key: str, storage_path: Optional[str] = None):
        self.secret_key = secret_key.encode("utf-8")
        self.storage_path = storage_path
        self.chain: List[AuditBlock] = []
        if self.storage_path and os.path.exists(self.storage_path):
            self._load_chain()
        if not self.chain:
            self._create_genesis_block()

    def _compute_sha256(self, data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _compute_hmac(self, message: str) -> str:
        return hmac.new(self.secret_key, message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _compute_merkle_root(self, hashes: List[str]) -> str:
        if not hashes:
            return self.GENESIS_HASH
        current_layer = list(hashes)
        while len(current_layer) > 1:
            if len(current_layer) % 2 != 0:
                current_layer.append(current_layer[-1])
            next_layer = []
            for i in range(0, len(current_layer), 2):
                combined = current_layer[i] + current_layer[i + 1]
                next_layer.append(self._compute_sha256(combined))
            current_layer = next_layer
        return current_layer[0]

    def _create_genesis_block(self) -> None:
        self.record_event(
            actor="STANZA_KERNEL",
            action="GENESIS_INITIALIZATION",
            payload={"status": "initialized", "version": "3.2.0", "os": "ARA_OS_12"},
        )

    def record_event(self, actor: str, action: str, payload: Dict[str, Any]) -> AuditBlock:
        index = len(self.chain)
        timestamp = time.time()
        serialized_payload = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = self._compute_sha256(serialized_payload)
        previous_hash = self.chain[-1].block_hash if self.chain else self.GENESIS_HASH

        historical_hashes = [b.payload_hash for b in self.chain] + [payload_hash]
        merkle_root = self._compute_merkle_root(historical_hashes)

        raw_block_string = f"{index}|{timestamp:.6f}|{actor}|{action}|{payload_hash}|{previous_hash}|{merkle_root}"
        signature = self._compute_hmac(raw_block_string)
        block_hash = self._compute_sha256(f"{raw_block_string}|{signature}")

        block = AuditBlock(
            index=index,
            timestamp=timestamp,
            actor=actor,
            action=action,
            payload_hash=payload_hash,
            previous_hash=previous_hash,
            merkle_root=merkle_root,
            signature=signature,
            block_hash=block_hash,
        )
        self.chain.append(block)
        self._persist()
        return block

    def verify_integrity(self) -> Dict[str, Any]:
        for i, block in enumerate(self.chain):
            expected_prev = self.GENESIS_HASH if i == 0 else self.chain[i - 1].block_hash
            if block.previous_hash != expected_prev:
                return {
                    "valid": False,
                    "corrupted_index": i,
                    "reason": "Broken previous_hash chain link",
                }

            raw_block_string = (
                f"{block.index}|{block.timestamp:.6f}|{block.actor}|{block.action}|"
                f"{block.payload_hash}|{block.previous_hash}|{block.merkle_root}"
            )
            expected_sig = self._compute_hmac(raw_block_string)
            if not hmac.compare_digest(block.signature, expected_sig):
                return {
                    "valid": False,
                    "corrupted_index": i,
                    "reason": "Invalid HMAC signature",
                }

            expected_hash = self._compute_sha256(f"{raw_block_string}|{block.signature}")
            if block.block_hash != expected_hash:
                return {
                    "valid": False,
                    "corrupted_index": i,
                    "reason": "Block hash mismatch",
                }

        return {
            "valid": True,
            "total_blocks": len(self.chain),
            "latest_merkle_root": self.chain[-1].merkle_root if self.chain else self.GENESIS_HASH,
            "latest_block_hash": self.chain[-1].block_hash if self.chain else self.GENESIS_HASH,
        }

    def _persist(self) -> None:
        if not self.storage_path:
            return
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump([asdict(b) for b in self.chain], f, indent=2)

    def _load_chain(self) -> None:
        if not self.storage_path:
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.chain = [AuditBlock(**item) for item in data]
        except Exception:
            self.chain = []
