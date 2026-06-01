import math
import re
from collections import Counter
from io import BytesIO

from pypdf import PdfReader


def extract_text_from_upload(uploaded_file) -> str:
    """Extract plain text from a Streamlit uploaded txt, md, or pdf file."""
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()

    if name.endswith(".pdf"):
        return extract_pdf_text(data)
    if name.endswith(".txt") or name.endswith(".md"):
        return decode_text(data)

    raise ValueError("暂时只支持 txt、md、pdf 文件。")


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"[第 {index} 页]\n{text.strip()}")
    return "\n\n".join(pages).strip()


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore").strip()


def retrieve_relevant_snippets(source_text: str, query: str, limit: int = 4) -> str:
    """Return relevant chunks ranked by local TF-IDF vector similarity."""
    if not source_text.strip() or not query.strip():
        return ""

    chunks = split_source(source_text)
    chunk_tokens = [tokenize(chunk) for chunk in chunks]
    document_frequencies = count_document_frequencies(chunk_tokens)
    query_vector = build_tfidf_vector(
        tokenize(query),
        document_frequencies,
        len(chunks),
    )
    scored = []

    for chunk, tokens in zip(chunks, chunk_tokens):
        chunk_vector = build_tfidf_vector(
            tokens,
            document_frequencies,
            len(chunks),
        )
        score = cosine_similarity(query_vector, chunk_vector)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = scored[:limit]
    return "\n\n---\n\n".join(
        f"[相关片段 {index}｜相似度 {score:.2f}]\n{trim_text(chunk, 900)}"
        for index, (score, chunk) in enumerate(chosen, start=1)
    )


def split_source(text: str, max_chars: int = 900, overlap_chars: int = 120) -> list[str]:
    """Split book text into compact chunks while keeping neighboring context."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    chunks = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(split_long_text(paragraph, max_chars, overlap_chars))
            continue

        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= max_chars:
            buffer = candidate
        else:
            chunks.append(buffer)
            overlap = buffer[-overlap_chars:].strip()
            with_overlap = f"{overlap}\n\n{paragraph}".strip()
            buffer = with_overlap if len(with_overlap) <= max_chars else paragraph

    if buffer:
        chunks.append(buffer)

    return chunks


def split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks = []
    step = max_chars - overlap_chars
    for start in range(0, len(text), step):
        chunk = text[start:start + max_chars].strip()
        if chunk:
            chunks.append(chunk)
        if start + max_chars >= len(text):
            break
    return chunks


def tokenize(text: str) -> list[str]:
    """Create lightweight Chinese-friendly tokens without external model downloads."""
    lowered = text.lower()
    latin_tokens = re.findall(r"[a-z0-9_]+", lowered)
    chinese_sequences = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese_tokens = []

    for sequence in chinese_sequences:
        for size in (2, 3):
            chinese_tokens.extend(
                sequence[index:index + size]
                for index in range(len(sequence) - size + 1)
            )

    return latin_tokens + chinese_tokens


def count_document_frequencies(documents: list[list[str]]) -> Counter:
    frequencies = Counter()
    for tokens in documents:
        frequencies.update(set(tokens))
    return frequencies


def build_tfidf_vector(
    tokens: list[str],
    document_frequencies: Counter,
    document_count: int,
) -> dict[str, float]:
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    vector = {}

    for token, count in counts.items():
        term_frequency = count / total
        inverse_document_frequency = math.log(
            (1 + document_count) / (1 + document_frequencies.get(token, 0))
        ) + 1
        vector[token] = term_frequency * inverse_document_frequency

    return vector


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0

    shared_tokens = left.keys() & right.keys()
    dot_product = sum(left[token] * right[token] for token in shared_tokens)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if not left_norm or not right_norm:
        return 0.0

    return dot_product / (left_norm * right_norm)


def trim_text(text: str, max_chars: int) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= max_chars:
        return one_line
    return f"{one_line[:max_chars]}..."
