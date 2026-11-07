from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List


@dataclass
class SecurityVerdict:
    is_safe: bool
    threat_score: float
    detected_vectors: List[str] = field(default_factory=list)
    sanitized_payload: str = ""
    shannon_entropy: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptFirewall:
    """
    Zero-Trust Linguistic & Structural Firewall.
    Detects Prompt Injection, Jailbreaks, Shell/SQL Injection, and Obfuscated Payloads.
    """

    INJECTION_PATTERNS = {
        "SYSTEM_OVERRIDE": re.compile(
            r"(ignore\s+(all\s+)?(previous|prior)\s+instructions|disregard\s+system\s+prompt|you\s+are\s+now\s+in\s+developer\s+mode)",
            re.IGNORECASE,
        ),
        "ROLE_HIJACKING": re.compile(
            r"(act\s+as\s+DAN|do\s+anything\s+now|bypass\s+safety\s+filters|unrestricted\s+mode)",
            re.IGNORECASE,
        ),
        "COMMAND_EXECUTION": re.compile(
            r"(;\s*rm\s+-rf|&&\s*curl\s+|\|\s*bash|\$\(whoami\)|`cat\s+/etc/passwd`)",
            re.IGNORECASE,
        ),
        "PYTHON_SANDBOX_ESCAPE": re.compile(
            r"(__import__|__subclasses__|__builtins__|__globals__|os\.system|subprocess\.Popen)",
            re.IGNORECASE,
        ),
        "SQL_INJECTION": re.compile(
            r"(UNION\s+SELECT\s+|DROP\s+TABLE\s+|OR\s+1=1\s*--)",
            re.IGNORECASE,
        ),
    }

    def __init__(self, strict_mode: bool = True, max_entropy_threshold: float = 6.2):
        self.strict_mode = strict_mode
        self.max_entropy_threshold = max_entropy_threshold

    @staticmethod
    def calculate_entropy(text: str) -> float:
        if not text:
            return 0.0
        freq: Dict[str, int] = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        length = len(text)
        return -sum((count / length) * math.log2(count / length) for count in freq.values())

    def inspect(self, payload: str) -> SecurityVerdict:
        detected: List[str] = []
        threat_score = 0.0

        for vector_name, pattern in self.INJECTION_PATTERNS.items():
            if pattern.search(payload):
                detected.append(vector_name)
                threat_score += 0.45

        entropy = self.calculate_entropy(payload)
        if entropy > self.max_entropy_threshold and len(payload) > 64:
            detected.append("HIGH_ENTROPY_OBFUSCATION")
            threat_score += 0.30

        threat_score = min(1.0, round(threat_score, 4))
        is_safe = threat_score < 0.40 if self.strict_mode else threat_score < 0.75

        sanitized = payload
        if not is_safe:
            for _, pattern in self.INJECTION_PATTERNS.items():
                sanitized = pattern.sub("[REDACTED_BY_STANZA_SHIELD]", sanitized)

        return SecurityVerdict(
            is_safe=is_safe,
            threat_score=threat_score,
            detected_vectors=detected,
            sanitized_payload=sanitized,
            shannon_entropy=round(entropy, 4),
            metadata={"length": len(payload), "strict_mode": self.strict_mode},
        )
