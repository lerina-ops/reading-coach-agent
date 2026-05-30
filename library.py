import re
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
    """Return a few relevant chunks from a book source using simple keyword scoring."""
    if not source_text.strip() or not query.strip():
        return ""

    chunks = split_source(source_text)
    query_terms = extract_query_terms(query)
    scored = []

    for chunk in chunks:
        score = score_chunk(chunk, query_terms)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = [chunk for _, chunk in scored[:limit]]
    if not chosen:
        chosen = chunks[: min(limit, len(chunks))]

    return "\n\n---\n\n".join(trim_text(chunk, 900) for chunk in chosen)


def split_source(text: str, max_chars: int = 900) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    chunks = []

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue
        for start in range(0, len(paragraph), max_chars):
            chunk = paragraph[start:start + max_chars].strip()
            if chunk:
                chunks.append(chunk)

    return chunks


def extract_query_terms(query: str) -> set[str]:
    words = set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", query))
    chinese_chars = {char for char in query if "\u4e00" <= char <= "\u9fff"}
    return words | chinese_chars


def score_chunk(chunk: str, query_terms: set[str]) -> int:
    lowered = chunk.lower()
    score = 0
    for term in query_terms:
        if not term:
            continue
        score += lowered.count(term.lower())
    return score


def trim_text(text: str, max_chars: int) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= max_chars:
        return one_line
    return f"{one_line[:max_chars]}..."
