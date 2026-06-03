import json
import mimetypes
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

import certifi


class SupabaseError(RuntimeError):
    """Readable error raised when a Supabase request fails."""


class SupabaseClient:
    def __init__(self, url: str, publishable_key: str, access_token: str = ""):
        self.url = url.rstrip("/")
        self.publishable_key = publishable_key.strip()
        self.access_token = access_token.strip()
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    def sign_up(self, email: str, password: str) -> dict:
        return self._request(
            "POST",
            "/auth/v1/signup",
            payload={"email": email.strip(), "password": password},
            use_user_token=False,
        )

    def sign_in(self, email: str, password: str) -> dict:
        return self._request(
            "POST",
            "/auth/v1/token?grant_type=password",
            payload={"email": email.strip(), "password": password},
            use_user_token=False,
        )

    def sign_out(self) -> None:
        if self.access_token:
            self._request("POST", "/auth/v1/logout")

    def get_books(self) -> list[dict]:
        return self._request("GET", "/rest/v1/books?select=*&order=created_at.asc")

    def add_book(self, user_id: str, title: str, author: str, purpose: str) -> dict:
        rows = self._request(
            "POST",
            "/rest/v1/books",
            payload={
                "user_id": user_id,
                "title": title.strip(),
                "author": author.strip(),
                "purpose": purpose.strip(),
            },
            prefer="return=representation",
        )
        return rows[0]

    def find_book(self, book_id: str) -> dict:
        rows = self._request(
            "GET",
            f"/rest/v1/books?id=eq.{quote(book_id)}&select=*",
        )
        if not rows:
            raise SupabaseError("找不到这本书，或者你没有访问权限。")
        return rows[0]

    def get_records(self, book_id: str | None = None) -> list[dict]:
        suffix = "&order=created_at.asc"
        if book_id:
            suffix = f"&book_id=eq.{quote(book_id)}{suffix}"
        return self._request("GET", f"/rest/v1/reading_records?select=*{suffix}")

    def add_reading_record(
        self,
        user_id: str,
        book_id: str,
        chapter: str,
        today_goal: str,
        excerpt: str,
        confusion: str,
        feedback: str,
    ) -> dict:
        rows = self._request(
            "POST",
            "/rest/v1/reading_records",
            payload={
                "user_id": user_id,
                "book_id": book_id,
                "chapter": chapter.strip(),
                "today_goal": today_goal.strip(),
                "excerpt": excerpt.strip(),
                "confusion": confusion.strip(),
                "feedback": feedback.strip(),
            },
            prefer="return=representation",
        )
        return rows[0]

    def get_chat_messages(self, book_id: str) -> list[dict]:
        return self._request(
            "GET",
            f"/rest/v1/chat_messages?book_id=eq.{quote(book_id)}"
            "&select=*&order=created_at.asc",
        )

    def add_chat_message(
        self,
        user_id: str,
        book_id: str,
        role: str,
        content: str,
    ) -> dict:
        rows = self._request(
            "POST",
            "/rest/v1/chat_messages",
            payload={
                "user_id": user_id,
                "book_id": book_id,
                "role": role,
                "content": content.strip(),
            },
            prefer="return=representation",
        )
        return rows[0]

    def clear_book_chat(self, book_id: str) -> None:
        self._request(
            "DELETE",
            f"/rest/v1/chat_messages?book_id=eq.{quote(book_id)}",
        )

    def save_book_source(
        self,
        user_id: str,
        book_id: str,
        filename: str,
        text: str,
        raw_bytes: bytes,
        content_type: str | None = None,
    ) -> dict:
        # Storage object keys stay ASCII-safe. The original display filename is
        # still saved in book_sources so users continue seeing their real title.
        suffix = Path(filename).suffix.lower()
        safe_suffix = suffix if re_safe_suffix(suffix) else ""
        storage_filename = f"{uuid.uuid4().hex}{safe_suffix}"
        storage_path = f"{user_id}/{book_id}/{storage_filename}"
        self._request_bytes(
            "POST",
            f"/storage/v1/object/book-files/{quote_storage_path(storage_path)}",
            raw_bytes,
            content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
            extra_headers={"x-upsert": "true"},
        )

        rows = self._request(
            "POST",
            "/rest/v1/book_sources?on_conflict=book_id",
            payload={
                "user_id": user_id,
                "book_id": book_id,
                "filename": filename,
                "text_content": text,
                "char_count": len(text),
                "updated_at": datetime.now().astimezone().isoformat(),
            },
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    def get_book_source(self, book_id: str) -> dict | None:
        rows = self._request(
            "GET",
            f"/rest/v1/book_sources?book_id=eq.{quote(book_id)}&select=*",
        )
        if not rows:
            return None

        row = rows[0]
        return {
            "text": row.get("text_content", ""),
            "filename": row.get("filename", "source.txt"),
            "char_count": row.get("char_count", 0),
            "updated_at": format_timestamp(row.get("updated_at", "")),
        }

    def _request(
        self,
        method: str,
        path: str,
        payload=None,
        prefer: str = "",
        use_user_token: bool = True,
    ):
        headers = {
            "apikey": self.publishable_key,
            "Content-Type": "application/json",
        }
        if use_user_token and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        if prefer:
            headers["Prefer"] = prefer

        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        return self._open_json(request)

    def _request_bytes(
        self,
        method: str,
        path: str,
        data: bytes,
        content_type: str,
        extra_headers: dict | None = None,
    ):
        headers = {
            "apikey": self.publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": content_type,
        }
        headers.update(extra_headers or {})
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request):
        try:
            with urllib.request.urlopen(
                request,
                timeout=60,
                context=self.ssl_context,
            ) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise SupabaseError(f"Supabase HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise SupabaseError(f"Supabase 网络连接失败：{exc.reason}") from exc


def quote(value: str) -> str:
    return urllib.parse.quote(str(value), safe="")


def quote_storage_path(value: str) -> str:
    """Encode object-path segments while preserving Storage folder separators."""
    return "/".join(
        urllib.parse.quote(segment, safe="")
        for segment in str(value).split("/")
    )


def re_safe_suffix(value: str) -> bool:
    return bool(value) and all(
        char.isascii() and (char.isalnum() or char in {".", "-", "_"})
        for char in value
    )


def format_timestamp(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def build_book_markdown(book: dict, records: list[dict], messages: list[dict]) -> str:
    lines = [
        f"# 《{book['title']}》读书笔记",
        "",
        f"- 作者：{book.get('author') or '未填写'}",
        f"- 阅读目的：{book.get('purpose') or '未填写'}",
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
                    f"- 记录时间：{format_timestamp(record.get('created_at', ''))}",
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

    if messages:
        lines.extend(
            [
                "## 陪读会话",
                "",
                (
                    f"> 这本书有 {len(messages)} 条底层对话消息。"
                    "为了保持笔记整洁，导出时不再逐条列出；"
                    "请在长椅点击“结束阅读并保存到回忆步道”，"
                    "把一次阅读中的对话合并为上方的阅读记录。"
                ),
                "",
            ]
        )

    return "\n".join(lines)
