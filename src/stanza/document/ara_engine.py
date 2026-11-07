from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List


@dataclass
class DocumentSection:
    level: int
    title: str
    content: str
    word_count: int
    section_hash: str


@dataclass
class DocumentIntelligenceReport:
    document_fingerprint: str
    ara_os_version: str
    total_words: int
    total_sentences: int
    flesch_reading_ease: float
    reading_time_seconds: float
    sections: List[DocumentSection] = field(default_factory=list)
    code_blocks_detected: int = 0
    key_terms: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ARADocumentIntelligenceEngine:
    """
    Intelligent Document Agent Engine for ARA OS 12.
    Provides deep structural document parsing, Markdown/Hierarchy extraction,
    Flesch-Kincaid readability telemetry, key-term TF ranking, and SHA-256 section fingerprinting.
    """

    STOPWORDS = {
        "the", "and", "for", "that", "this", "with", "from", "are", "was", "were",
        "have", "has", "had", "not", "but", "what", "all", "when", "can", "your",
        "para", "com", "uma", "dos", "das", "por", "mais", "como", "mas", "foi",
    }

    def __init__(self, ara_os_version: str = "ARA-OS-12.4-SOVEREIGN"):
        self.ara_os_version = ara_os_version

    @staticmethod
    def _count_syllables(word: str) -> int:
        word_clean = re.sub(r"[^a-z]", "", word.lower())
        if len(word_clean) <= 3:
            return 1
        vowels = "aeiouy"
        count = 0
        prev_is_vowel = False
        for char in word_clean:
            is_vowel = char in vowels
            if is_vowel and not prev_is_vowel:
                count += 1
            prev_is_vowel = is_vowel
        if word_clean.endswith("e") and count > 1:
            count -= 1
        return max(1, count)

    def analyze_document(self, raw_document: str) -> DocumentIntelligenceReport:
        doc_hash = hashlib.sha256(raw_document.encode("utf-8")).hexdigest()
        words = re.findall(r"[A-Za-zÀ-ÿ0-9_]+", raw_document)
        total_words = len(words)
        sentences = [s for s in re.split(r"[.!?]+", raw_document) if s.strip()]
        total_sentences = max(1, len(sentences))

        # Flesch Reading Ease calculation
        total_syllables = sum(self._count_syllables(w) for w in words) if words else 1
        words_per_sentence = total_words / total_sentences
        syllables_per_word = total_syllables / max(1, total_words)
        flesch_score = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
        flesch_clamped = round(max(0.0, min(100.0, flesch_score)), 2)

        # Reading time (average 220 WPM)
        reading_time_sec = round((total_words / 220.0) * 60.0, 2)

        # Extract Markdown / Document sections
        sections: List[DocumentSection] = []
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(heading_pattern.finditer(raw_document))

        if matches:
            for idx, match in enumerate(matches):
                level = len(match.group(1))
                title = match.group(2).strip()
                start_pos = match.end()
                end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_document)
                body = raw_document[start_pos:end_pos].strip()
                sec_words = len(re.findall(r"\w+", body))
                sec_hash = hashlib.sha256(f"{title}:{body}".encode("utf-8")).hexdigest()[:16]
                sections.append(
                    DocumentSection(
                        level=level,
                        title=title,
                        content=body,
                        word_count=sec_words,
                        section_hash=sec_hash,
                    )
                )
        else:
            body_clean = raw_document.strip()
            sections.append(
                DocumentSection(
                    level=1,
                    title="ROOT_DOCUMENT_BODY",
                    content=body_clean,
                    word_count=total_words,
                    section_hash=doc_hash[:16],
                )
            )

        # Detect fenced code blocks
        code_blocks = len(re.findall(r"```[\s\S]*?```", raw_document))

        # Extract top key terms
        freq: Dict[str, int] = {}
        for w in words:
            w_low = w.lower()
            if len(w_low) >= 4 and w_low not in self.STOPWORDS and not w_low.isdigit():
                freq[w_low] = freq.get(w_low, 0) + 1
        top_terms = [k for k, _ in sorted(freq.items(), key=lambda item: item[1], reverse=True)[:8]]

        return DocumentIntelligenceReport(
            document_fingerprint=doc_hash,
            ara_os_version=self.ara_os_version,
            total_words=total_words,
            total_sentences=total_sentences,
            flesch_reading_ease=flesch_clamped,
            reading_time_seconds=reading_time_sec,
            sections=sections,
            code_blocks_detected=code_blocks,
            key_terms=top_terms,
            metadata={
                "section_count": len(sections),
                "avg_words_per_sentence": round(words_per_sentence, 2),
            },
        )
