import ast
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class StanzaSegment:
    stanza_id: int
    raw_text: str
    tokens: List[str]
    intent_category: str
    entities: List[Dict[str, str]]
    complexity_score: float
    syntactic_density: float


@dataclass
class CodeASTAnalysis:
    is_valid_python: bool
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    cyclomatic_complexity: int = 1
    security_warnings: List[str] = field(default_factory=list)
    error_message: str = ""


class StanzaLinguisticEngine:
    """
    Neuro-Symbolic Linguistic & Structural Parser ('Stanza' Core).
    Decomposes unstructured natural language and source code into semantic stanzas,
    extracts entities, classifies intents, and inspects Python AST structures.
    """

    INTENT_KEYWORDS = {
        "CODE_SYNTHESIS": {"implement", "code", "function", "class", "script", "algorithm", "refactor", "python", "def"},
        "SECURITY_AUDIT": {"audit", "vulnerability", "exploit", "pentest", "cve", "secure", "hash", "firewall", "encrypt"},
        "DATA_ANALYSIS": {"analyze", "metrics", "calculate", "statistics", "dataset", "aggregate", "report", "matrix"},
        "SYSTEM_ARCHITECTURE": {"architecture", "dag", "orchestrate", "pipeline", "microservice", "deploy", "docker", "kernel"},
    }

    ENTITY_PATTERNS = {
        "IPV4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "URL": re.compile(r"https?://[^\s/$.?#].[^\s]*"),
        "FILE_PATH": re.compile(r"(?:/[a-zA-Z0-9._-]+){2,}"),
        "CVE_ID": re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE),
        "HEX_HASH": re.compile(r"\b[a-fA-F0-9]{32,64}\b"),
    }

    DANGEROUS_AST_CALLS = {"eval", "exec", "compile", "open", "system", "popen"}

    def tokenize(self, text: str) -> List[str]:
        return re.findall(r"[A-Za-z0-9_]+|[^\w\s]", text.lower())

    def classify_intent(self, tokens: List[str]) -> str:
        token_set = set(tokens)
        scores: Dict[str, int] = {}
        for intent, keywords in self.INTENT_KEYWORDS.items():
            scores[intent] = len(token_set.intersection(keywords))
        best_intent = max(scores, key=scores.get)
        return best_intent if scores[best_intent] > 0 else "GENERAL_REASONING"

    def extract_entities(self, text: str) -> List[Dict[str, str]]:
        entities: List[Dict[str, str]] = []
        for label, pattern in self.ENTITY_PATTERNS.items():
            for match in pattern.finditer(text):
                entities.append({"type": label, "value": match.group(0)})
        return entities

    def segment_into_stanzas(self, document: str) -> List[StanzaSegment]:
        raw_blocks = [b.strip() for b in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", document) if b.strip()]
        if not raw_blocks and document.strip():
            raw_blocks = [document.strip()]

        stanzas: List[StanzaSegment] = []
        for idx, block in enumerate(raw_blocks):
            tokens = self.tokenize(block)
            word_tokens = [t for t in tokens if t.isalnum()]
            unique_ratio = len(set(word_tokens)) / max(1, len(word_tokens))
            avg_word_len = sum(len(w) for w in word_tokens) / max(1, len(word_tokens))

            complexity = round(min(1.0, (avg_word_len / 10.0) * 0.5 + unique_ratio * 0.5), 4)
            syntactic_density = round(len(word_tokens) / max(1, len(tokens)), 4)

            stanzas.append(
                StanzaSegment(
                    stanza_id=idx + 1,
                    raw_text=block,
                    tokens=tokens,
                    intent_category=self.classify_intent(word_tokens),
                    entities=self.extract_entities(block),
                    complexity_score=complexity,
                    syntactic_density=syntactic_density,
                )
            )
        return stanzas

    def analyze_python_ast(self, code_str: str) -> CodeASTAnalysis:
        try:
            tree = ast.parse(code_str)
        except SyntaxError as exc:
            return CodeASTAnalysis(is_valid_python=False, error_message=f"SyntaxError: {exc.msg} at line {exc.lineno}")

        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []
        warnings: List[str] = []
        complexity = 1

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
                complexity += 1
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.ExceptHandler, ast.With)):
                complexity += 1
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in self.DANGEROUS_AST_CALLS:
                    warnings.append(f"Potentially unsafe call '{func_name}' detected at line {getattr(node, 'lineno', '?')}")

        return CodeASTAnalysis(
            is_valid_python=True,
            functions=functions,
            classes=classes,
            imports=list(set(imports)),
            cyclomatic_complexity=complexity,
            security_warnings=warnings,
        )
