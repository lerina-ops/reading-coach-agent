import json
import re
import uuid
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EXPORT_DIR = BASE_DIR / "exports"
BOOK_SOURCES_DIR = DATA_DIR / "book_sources"
BOOKS_PATH = DATA_DIR / "books.json"
RECORDS_PATH = DATA_DIR / "reading_records.json"
CHAT_PATH = DATA_DIR / "chat_messages.json"


def get_books() -> list[dict]:
    return load_json(BOOKS_PATH, default=[])


def get_records() -> list[dict]:
    return load_json(RECORDS_PATH, default=[])


def get_chat_messages(book_id: str | None = None) -> list[dict]:
    messages = load_json(CHAT_PATH, default=[])
    if book_id is None:
        return messages
    return [message for message in messages if message["book_id"] == book_id]


def add_book(title: str, author: str, purpose: str) -> dict:
    books = get_books()
    book = {
        "id": new_id(),
        "title": title.strip(),
        "author": author.strip(),
        "purpose": purpose.strip(),
        "created_at": now_text(),
    }
    books.append(book)
    save_json(BOOKS_PATH, books)
    return book


def find_book(book_id: str) -> dict:
    for book in get_books():
        if book["id"] == book_id:
            return book
    raise ValueError(f"找不到书籍：{book_id}")


def add_reading_record(
    book_id: str,
    chapter: str,
    today_goal: str,
    excerpt: str,
    confusion: str,
    feedback: str,
) -> dict:
    records = get_records()
    record = {
        "id": new_id(),
        "book_id": book_id,
        "chapter": chapter.strip(),
        "today_goal": today_goal.strip(),
        "excerpt": excerpt.strip(),
        "confusion": confusion.strip(),
        "feedback": feedback.strip(),
        "created_at": now_text(),
    }
    records.append(record)
    save_json(RECORDS_PATH, records)
    return record


def add_chat_message(book_id: str, role: str, content: str) -> dict:
    messages = get_chat_messages()
    message = {
        "id": new_id(),
        "book_id": book_id,
        "role": role,
        "content": content.strip(),
        "created_at": now_text(),
    }
    messages.append(message)
    save_json(CHAT_PATH, messages)
    return message


def save_book_source(book_id: str, filename: str, text: str) -> dict:
    source_dir = BOOK_SOURCES_DIR / book_id
    source_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "book_id": book_id,
        "filename": filename,
        "char_count": len(text),
        "updated_at": now_text(),
    }
    (source_dir / "source.txt").write_text(text, encoding="utf-8")
    save_json(source_dir / "source_meta.json", meta)
    return meta


def get_book_source(book_id: str) -> dict | None:
    source_dir = BOOK_SOURCES_DIR / book_id
    text_path = source_dir / "source.txt"
    meta_path = source_dir / "source_meta.json"
    if not text_path.exists():
        return None

    meta = load_json(meta_path, default={})
    return {
        "text": text_path.read_text(encoding="utf-8"),
        "filename": meta.get("filename", "source.txt"),
        "char_count": meta.get("char_count", 0),
        "updated_at": meta.get("updated_at", ""),
    }


def clear_book_chat(book_id: str) -> None:
    messages = [
        message for message in get_chat_messages()
        if message["book_id"] != book_id
    ]
    save_json(CHAT_PATH, messages)


def export_book_markdown(book_id: str) -> Path:
    book = find_book(book_id)
    source = get_book_source(book_id)
    records = [item for item in get_records() if item["book_id"] == book_id]
    chat_messages = get_chat_messages(book_id)
    records.sort(key=lambda item: item["created_at"])
    chat_messages.sort(key=lambda item: item["created_at"])

    lines = [
        f"# 《{book['title']}》读书笔记",
        "",
        f"- 作者：{book.get('author') or '未填写'}",
        f"- 阅读目的：{book.get('purpose') or '未填写'}",
        f"- 书籍资料：{source['filename'] if source else '未上传'}",
        f"- 导出时间：{now_text()}",
        "",
    ]

    if not records:
        lines.append("> 这本书还没有阅读记录。")
    else:
        for index, record in enumerate(records, start=1):
            lines.extend(
                [
                    f"## {index}. {record['chapter']}",
                    "",
                    f"- 记录时间：{record['created_at']}",
                    f"- 今日目标：{record.get('today_goal') or '未填写'}",
                    "",
                    "### 书摘",
                    "",
                    record.get("excerpt") or "未填写",
                    "",
                    "### 我的困惑",
                    "",
                    record.get("confusion") or "未填写",
                    "",
                    "### 陪读反馈",
                    "",
                    record.get("feedback") or "未生成",
                    "",
                ]
            )

    if chat_messages:
        lines.extend(["## 陪读对话", ""])
        for message in chat_messages:
            role_name = "我" if message["role"] == "user" else "读书教练"
            lines.extend(
                [
                    f"### {role_name}｜{message['created_at']}",
                    "",
                    message.get("content") or "",
                    "",
                ]
            )

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(book['title'])}_reading_notes.md"
    output_path = EXPORT_DIR / filename
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def new_id() -> str:
    return uuid.uuid4().hex


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_filename(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", text.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "book"
