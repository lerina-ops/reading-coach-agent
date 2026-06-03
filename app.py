import os
import importlib
from datetime import datetime
from pathlib import Path

import streamlit as st

try:
    import reading_coach.coach as coach_module
    from reading_coach.cloud_storage import SupabaseClient, build_book_markdown
    from reading_coach.library import extract_text_from_upload, retrieve_relevant_snippets
    from reading_coach.storage import (
        add_book as local_add_book,
        add_chat_message as local_add_chat_message,
        add_reading_record as local_add_reading_record,
        clear_book_chat as local_clear_book_chat,
        export_book_markdown as local_export_book_markdown,
        find_book as local_find_book,
        get_book_source as local_get_book_source,
        get_books as local_get_books,
        get_chat_messages as local_get_chat_messages,
        get_records as local_get_records,
        save_book_source as local_save_book_source,
    )
except ModuleNotFoundError:
    import coach as coach_module
    from cloud_storage import SupabaseClient, build_book_markdown
    from library import extract_text_from_upload, retrieve_relevant_snippets
    from storage import (
        add_book as local_add_book,
        add_chat_message as local_add_chat_message,
        add_reading_record as local_add_reading_record,
        clear_book_chat as local_clear_book_chat,
        export_book_markdown as local_export_book_markdown,
        find_book as local_find_book,
        get_book_source as local_get_book_source,
        get_books as local_get_books,
        get_chat_messages as local_get_chat_messages,
        get_records as local_get_records,
        save_book_source as local_save_book_source,
    )


coach_module = importlib.reload(coach_module)
generate_feedback = coach_module.generate_feedback
generate_chat_reply = coach_module.generate_chat_reply
test_model_connection = coach_module.test_model_connection


BASE_DIR = Path(__file__).parent
PROMPT_PATH = BASE_DIR / "prompts" / "reading_coach.md"
if not PROMPT_PATH.exists():
    PROMPT_PATH = BASE_DIR / "reading_coach.md"
CHAT_MODES = [
    "温柔陪读者",
    "概念翻译官",
    "追问教练",
    "生活联想家",
    "笔记整理师",
]
MODE_HINTS = {
    "温柔陪读者": "先接住你的感受，再把问题慢慢讲清楚。",
    "概念翻译官": "把抽象概念翻成日常语言，少说术语。",
    "追问教练": "少给结论，多用一个关键问题带你往下想。",
    "生活联想家": "把书里的观点放进工作、关系和日常场景里看。",
    "笔记整理师": "把这轮对话收束成能复习、能继续修改的笔记。",
}
QUICK_PROMPTS = [
    "这段话是什么意思？",
    "给我举个生活例子",
    "你反问我一个问题",
    "我这样理解对吗？",
    "帮我整理成今天的笔记",
    "给我一个明天能做的小行动",
]
PARK_SCENES = [
    {
        "id": "bench",
        "name": "林荫长椅",
        "subtitle": "适合慢慢对话，把卡住的地方讲开。",
        "button": "去长椅陪读",
    },
    {
        "id": "table",
        "name": "草地书桌",
        "subtitle": "适合记录章节、书摘、困惑和今日反馈。",
        "button": "去书桌记录",
    },
    {
        "id": "pavilion",
        "name": "资料小亭",
        "subtitle": "适合上传书籍资料，让 Agent 有据可查。",
        "button": "去小亭整理",
    },
    {
        "id": "trail",
        "name": "回忆步道",
        "subtitle": "适合回看阅读时间线，导出长期笔记。",
        "button": "去步道复盘",
    },
]
SCENE_NAMES = {scene["id"]: scene["name"] for scene in PARK_SCENES}


st.set_page_config(
    page_title="陪我读书的 Agent",
    page_icon="📚",
    layout="wide",
)


st.markdown(
    """
    <style>
    :root {
        --coach-ink: #202124;
        --coach-muted: #68707a;
        --coach-line: #e7e2da;
        --coach-soft: #fbfaf7;
        --coach-panel: #ffffff;
        --coach-accent: #365f5c;
    }

    .stApp {
        background:
            linear-gradient(180deg, #fbfaf7 0%, #f6f3ee 48%, #faf9f6 100%);
        color: var(--coach-ink);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    [data-testid="stSidebar"] {
        background: #f3f0ea;
        border-right: 1px solid var(--coach-line);
    }

    .coach-hero {
        border: 1px solid var(--coach-line);
        background: rgba(255, 255, 255, 0.72);
        padding: 22px 24px;
        border-radius: 8px;
        margin-bottom: 18px;
    }

    .coach-hero h1 {
        font-size: 2rem;
        line-height: 1.2;
        margin: 0 0 8px;
        letter-spacing: 0;
    }

    .coach-hero p {
        color: var(--coach-muted);
        margin: 0;
        font-size: 0.98rem;
    }

    .coach-status {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin: 12px 0 4px;
    }

    .coach-stat {
        border: 1px solid var(--coach-line);
        background: var(--coach-panel);
        border-radius: 8px;
        padding: 12px 14px;
    }

    .coach-stat strong {
        display: block;
        font-size: 1.2rem;
        color: var(--coach-accent);
        margin-bottom: 2px;
    }

    .coach-stat span {
        color: var(--coach-muted);
        font-size: 0.86rem;
    }

    .coach-note {
        border-left: 3px solid var(--coach-accent);
        background: rgba(255, 255, 255, 0.7);
        padding: 10px 12px;
        border-radius: 0 8px 8px 0;
        color: var(--coach-muted);
        margin: 10px 0 12px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid var(--coach-line);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
        padding: 10px 12px;
    }

    div[data-testid="stChatMessage"] {
        border: 1px solid var(--coach-line);
        background: rgba(255, 255, 255, 0.76);
        border-radius: 8px;
        padding: 0.55rem 0.75rem;
        margin-bottom: 0.7rem;
    }

    button[kind="secondary"], button[kind="primary"] {
        border-radius: 6px !important;
    }

    .park-stage {
        position: relative;
        overflow: hidden;
        min-height: 260px;
        border: 1px solid var(--coach-line);
        border-radius: 8px;
        background: #dce9dc;
        margin: 10px 0 18px;
    }

    .park-sky {
        position: absolute;
        inset: 0 0 42% 0;
        background: linear-gradient(180deg, #d9e9ef 0%, #edf0df 100%);
    }

    .park-ground {
        position: absolute;
        inset: 42% 0 0 0;
        background: linear-gradient(180deg, #9fbd8f 0%, #d6cfaa 100%);
    }

    .park-path {
        position: absolute;
        left: 34%;
        bottom: -36%;
        width: 32%;
        height: 92%;
        background: #d8c59d;
        transform: perspective(240px) rotateX(56deg);
        border-left: 1px solid rgba(117, 91, 55, 0.18);
        border-right: 1px solid rgba(117, 91, 55, 0.18);
    }

    .park-tree {
        position: absolute;
        bottom: 22%;
        width: 42px;
        height: 96px;
        background: #7b6042;
        border-radius: 18px 18px 6px 6px;
    }

    .park-tree::before {
        content: "";
        position: absolute;
        left: -48px;
        top: -74px;
        width: 138px;
        height: 106px;
        border-radius: 48% 52% 54% 46%;
        background: #54795d;
        box-shadow: 26px 18px 0 #6f9463, -18px 22px 0 #7f9f6b;
    }

    .tree-left { left: 9%; }
    .tree-right { right: 11%; transform: scale(0.9); }

    .park-object {
        position: absolute;
        left: 50%;
        top: 54%;
        transform: translate(-50%, -50%);
        width: 160px;
        height: 92px;
        border-radius: 8px;
        background: #f7f2e8;
        border: 1px solid rgba(64, 70, 54, 0.22);
        box-shadow: 0 14px 30px rgba(67, 75, 55, 0.16);
    }

    .park-object::before,
    .park-object::after {
        content: "";
        position: absolute;
        background: #735d43;
    }

    .park-bench::before {
        left: 18px;
        right: 18px;
        top: 32px;
        height: 12px;
        border-radius: 6px;
    }

    .park-bench::after {
        left: 28px;
        right: 28px;
        bottom: 24px;
        height: 12px;
        border-radius: 6px;
    }

    .park-table::before {
        left: 28px;
        right: 28px;
        top: 30px;
        height: 16px;
        border-radius: 4px;
    }

    .park-table::after {
        left: 70px;
        top: 44px;
        width: 18px;
        height: 38px;
        border-radius: 4px;
    }

    .park-pavilion {
        width: 180px;
        height: 110px;
        background: transparent;
        border: 0;
        box-shadow: none;
    }

    .park-pavilion::before {
        left: 14px;
        right: 14px;
        top: 8px;
        height: 34px;
        background: #7f5f47;
        clip-path: polygon(50% 0, 100% 100%, 0 100%);
    }

    .park-pavilion::after {
        left: 40px;
        top: 42px;
        width: 100px;
        height: 64px;
        background: #f4ead4;
        border: 1px solid rgba(64, 70, 54, 0.2);
    }

    .park-trail::before {
        left: 22px;
        right: 22px;
        top: 28px;
        height: 10px;
        border-radius: 999px;
        background: #62756a;
        box-shadow: 0 20px 0 #8a9577, 0 40px 0 #b79c68;
    }

    .park-trail::after {
        right: 24px;
        top: 18px;
        width: 34px;
        height: 54px;
        border-radius: 18px 18px 4px 4px;
        background: #f5e7c8;
    }

    .park-sign {
        position: absolute;
        left: 50%;
        bottom: 18px;
        transform: translateX(-50%);
        padding: 12px 18px;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.76);
        border: 1px solid rgba(76, 84, 65, 0.22);
        text-align: center;
        min-width: min(520px, 86%);
        backdrop-filter: blur(8px);
    }

    .park-sign strong {
        display: block;
        color: var(--coach-accent);
        font-size: 1.1rem;
        margin-bottom: 4px;
    }

    .park-sign span {
        color: var(--coach-muted);
        font-size: 0.92rem;
    }

    .park-leaf {
        position: absolute;
        top: 48px;
        left: -24px;
        width: 16px;
        height: 8px;
        border-radius: 100% 0 100% 0;
        background: #9c7655;
        opacity: 0.58;
        animation: leaf-drift 13s linear infinite;
    }

    .park-leaf.second {
        top: 86px;
        animation-delay: 4s;
        animation-duration: 16s;
        background: #6f8f66;
    }

    @keyframes leaf-drift {
        from { transform: translateX(-30px) translateY(0) rotate(0deg); }
        55% { transform: translateX(58vw) translateY(22px) rotate(140deg); }
        to { transform: translateX(112vw) translateY(4px) rotate(260deg); }
    }

    .scene-card {
        border: 1px solid var(--coach-line);
        background: rgba(255, 255, 255, 0.78);
        border-radius: 8px;
        padding: 14px;
        min-height: 110px;
        margin-bottom: 8px;
    }

    .scene-card strong {
        display: block;
        color: var(--coach-ink);
        margin-bottom: 5px;
    }

    .scene-card span {
        color: var(--coach-muted);
        font-size: 0.9rem;
    }

    @media (max-width: 760px) {
        .coach-status {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def secret_value(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except FileNotFoundError:
        return ""


SUPABASE_URL = secret_value("SUPABASE_URL")
SUPABASE_KEY = secret_value("SUPABASE_PUBLISHABLE_KEY") or secret_value("SUPABASE_ANON_KEY")
CLOUD_MODE = bool(SUPABASE_URL and SUPABASE_KEY)


def render_cloud_login() -> None:
    st.title("陪我读书的 Agent")
    st.caption("登录后，你的书籍、资料和对话会保存到自己的云端空间。")
    login_tab, signup_tab = st.tabs(["登录", "注册"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("邮箱", key="login_email")
            password = st.text_input("密码", type="password", key="login_password")
            submitted = st.form_submit_button("登录")

        if submitted:
            try:
                result = SupabaseClient(SUPABASE_URL, SUPABASE_KEY).sign_in(email, password)
                st.session_state["supabase_access_token"] = result["access_token"]
                st.session_state["supabase_user"] = result["user"]
                st.rerun()
            except Exception as exc:
                st.error(f"登录失败：{exc}")

    with signup_tab:
        with st.form("signup_form"):
            email = st.text_input("注册邮箱", key="signup_email")
            password = st.text_input(
                "设置密码",
                type="password",
                key="signup_password",
                help="至少 6 位。不要使用你的邮箱密码。",
            )
            submitted = st.form_submit_button("创建账号")

        if submitted:
            try:
                result = SupabaseClient(SUPABASE_URL, SUPABASE_KEY).sign_up(email, password)
                if result.get("access_token"):
                    st.session_state["supabase_access_token"] = result["access_token"]
                    st.session_state["supabase_user"] = result["user"]
                    st.rerun()
                else:
                    st.success("注册成功。请先前往邮箱完成验证，再回来登录。")
            except Exception as exc:
                st.error(f"注册失败：{exc}")


if CLOUD_MODE and not st.session_state.get("supabase_access_token"):
    render_cloud_login()
    st.stop()


cloud_client = None
current_user = st.session_state.get("supabase_user", {})
current_user_id = current_user.get("id", "")
if CLOUD_MODE:
    cloud_client = SupabaseClient(
        SUPABASE_URL,
        SUPABASE_KEY,
        st.session_state["supabase_access_token"],
    )


def get_books() -> list[dict]:
    return cloud_client.get_books() if CLOUD_MODE else local_get_books()


def add_book(title: str, author: str, purpose: str) -> dict:
    if CLOUD_MODE:
        return cloud_client.add_book(current_user_id, title, author, purpose)
    return local_add_book(title, author, purpose)


def find_book(book_id: str) -> dict:
    return cloud_client.find_book(book_id) if CLOUD_MODE else local_find_book(book_id)


def get_records(book_id: str | None = None) -> list[dict]:
    if CLOUD_MODE:
        return cloud_client.get_records(book_id)
    records = local_get_records()
    if book_id is None:
        return records
    return [record for record in records if record["book_id"] == book_id]


def add_reading_record(**kwargs) -> dict:
    if CLOUD_MODE:
        return cloud_client.add_reading_record(current_user_id, **kwargs)
    return local_add_reading_record(**kwargs)


def get_chat_messages(book_id: str) -> list[dict]:
    if CLOUD_MODE:
        return cloud_client.get_chat_messages(book_id)
    return local_get_chat_messages(book_id)


def add_chat_message(book_id: str, role: str, content: str) -> dict:
    if CLOUD_MODE:
        return cloud_client.add_chat_message(current_user_id, book_id, role, content)
    return local_add_chat_message(book_id, role, content)


def clear_book_chat(book_id: str) -> None:
    if CLOUD_MODE:
        cloud_client.clear_book_chat(book_id)
    else:
        local_clear_book_chat(book_id)


def get_book_source(book_id: str) -> dict | None:
    if CLOUD_MODE:
        return cloud_client.get_book_source(book_id)
    return local_get_book_source(book_id)


def save_book_source(book_id: str, uploaded_file, text: str) -> dict:
    if CLOUD_MODE:
        return cloud_client.save_book_source(
            current_user_id,
            book_id,
            uploaded_file.name,
            text,
            uploaded_file.getvalue(),
            uploaded_file.type,
        )
    return local_save_book_source(book_id, uploaded_file.name, text)


def book_label(book: dict) -> str:
    author = book.get("author", "").strip()
    return f"{book['title']} - {author}" if author else book["title"]


def render_feedback(feedback: str) -> None:
    st.markdown(feedback)


def render_app_intro() -> None:
    st.markdown(
        """
        <div class="coach-hero">
            <h1>陪我读书的 Agent</h1>
            <p>把书摘、困惑、对话和复盘沉淀在同一本书里，慢慢形成你的长期阅读笔记。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_book_status(records_count: int, messages_count: int, has_source: bool) -> None:
    source_text = "已上传" if has_source else "未上传"
    st.markdown(
        f"""
        <div class="coach-status">
            <div class="coach-stat"><strong>{records_count}</strong><span>阅读记录</span></div>
            <div class="coach-stat"><strong>{messages_count}</strong><span>陪读对话</span></div>
            <div class="coach-stat"><strong>{source_text}</strong><span>书籍资料</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def latest_dialogue_pair(messages: list[dict]) -> tuple[str, str] | None:
    assistant_reply = ""
    user_question = ""
    for message in reversed(messages):
        if not assistant_reply and message.get("role") == "assistant":
            assistant_reply = message.get("content", "")
        elif assistant_reply and message.get("role") == "user":
            user_question = message.get("content", "")
            break

    if user_question and assistant_reply:
        return user_question, assistant_reply
    return None


def reading_session_key(book_id: str) -> str:
    return f"reading_session_{book_id}"


def start_reading_session(book_id: str, message_count: int) -> None:
    st.session_state[reading_session_key(book_id)] = {
        "started_at": datetime.now().isoformat(),
        "message_count": message_count,
    }


def get_reading_session(book_id: str) -> dict | None:
    return st.session_state.get(reading_session_key(book_id))


def clear_reading_session(book_id: str) -> None:
    st.session_state.pop(reading_session_key(book_id), None)


def format_duration(seconds: int) -> str:
    minutes, remaining_seconds = divmod(max(seconds, 0), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} 小时 {minutes} 分钟"
    if minutes:
        return f"{minutes} 分钟 {remaining_seconds} 秒"
    return f"{remaining_seconds} 秒"


def session_elapsed(session: dict) -> tuple[str, int]:
    started_at = datetime.fromisoformat(session["started_at"])
    seconds = int((datetime.now() - started_at).total_seconds())
    return format_duration(seconds), seconds


def format_dialogue_excerpt(messages: list[dict], max_items: int = 12) -> str:
    if not messages:
        return "本次阅读没有产生对话。"

    lines = []
    for message in messages[-max_items:]:
        role_name = "我" if message.get("role") == "user" else "读书教练"
        content = message.get("content", "").strip()
        if content:
            lines.append(f"**{role_name}**：{content}")
    return "\n\n".join(lines) or "本次阅读没有产生可整理的对话。"


def build_session_feedback(
    selected_book: dict,
    duration_text: str,
    session_messages: list[dict],
) -> str:
    user_messages = [message.get("content", "") for message in session_messages if message.get("role") == "user"]
    assistant_messages = [
        message.get("content", "")
        for message in session_messages
        if message.get("role") == "assistant"
    ]
    dialogue_excerpt = format_dialogue_excerpt(session_messages)
    focus_text = summarize_text(" ".join(user_messages), 220) if user_messages else "这次主要是安静阅读或整理资料。"
    note_text = summarize_text(" ".join(assistant_messages), 260) if assistant_messages else "还没有生成陪读回复。"

    return f"""
## 今日阅读笔记
- 书名：《{selected_book.get("title", "")}》
- 阅读时长：{duration_text}
- 本次重点：{focus_text}
- 陪读摘录：{note_text}

## 本次对话摘录
{dialogue_excerpt}

## 下次继续读
下次可以从这次最卡住的问题继续，也可以把其中一个观点整理成自己的生活例子。
""".strip()


def save_reading_session_as_record(
    selected_book: dict,
    all_messages: list[dict],
) -> dict | None:
    session = get_reading_session(selected_book["id"])
    if not session:
        return None

    start_count = int(session.get("message_count", 0))
    session_messages = all_messages[start_count:]
    duration_text, _ = session_elapsed(session)
    started_at = datetime.fromisoformat(session["started_at"])
    ended_at = datetime.now()
    dialogue_excerpt = format_dialogue_excerpt(session_messages)
    feedback = build_session_feedback(selected_book, duration_text, session_messages)

    record = add_reading_record(
        book_id=selected_book["id"],
        chapter=f"陪读会话｜{ended_at.strftime('%Y-%m-%d %H:%M')}",
        today_goal=(
            f"阅读时长：{duration_text}｜"
            f"开始：{started_at.strftime('%Y-%m-%d %H:%M')}｜"
            f"结束：{ended_at.strftime('%Y-%m-%d %H:%M')}"
        ),
        excerpt=dialogue_excerpt,
        confusion="本次阅读由陪读对话自动整理。",
        feedback=feedback,
    )
    clear_reading_session(selected_book["id"])
    return record


def save_latest_dialogue_as_record(book_id: str, messages: list[dict]) -> bool:
    pair = latest_dialogue_pair(messages)
    if not pair:
        return False

    user_question, assistant_reply = pair
    add_reading_record(
        book_id=book_id,
        chapter=f"陪读对话｜{datetime.now().strftime('%Y-%m-%d')}",
        today_goal="把一次对话式阅读沉淀为可复习的阅读记录。",
        excerpt=user_question,
        confusion=user_question,
        feedback=assistant_reply,
    )
    return True


def render_park_visual(scene_id: str, title: str, subtitle: str, book_title: str = "") -> None:
    object_class = {
        "gate": "park-table",
        "map": "park-trail",
        "bench": "park-bench",
        "table": "park-table",
        "pavilion": "park-pavilion",
        "trail": "park-trail",
    }.get(scene_id, "park-bench")
    book_line = f"正在读：《{book_title}》" if book_title else "先在门口选一本今天要读的书"
    st.markdown(
        f"""
        <div class="park-stage">
            <div class="park-sky"></div>
            <div class="park-ground"></div>
            <div class="park-path"></div>
            <div class="park-tree tree-left"></div>
            <div class="park-tree tree-right"></div>
            <div class="park-object {object_class}"></div>
            <div class="park-leaf"></div>
            <div class="park-leaf second"></div>
            <div class="park-sign">
                <strong>{title}</strong>
                <span>{subtitle}<br>{book_line}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def go_to_scene(scene_id: str) -> None:
    st.session_state["park_scene"] = scene_id
    st.rerun()


def set_active_book(book_id: str) -> None:
    st.session_state["park_active_book_id"] = book_id


def get_active_book(books: list[dict]) -> dict | None:
    active_id = st.session_state.get("park_active_book_id", "")
    for book in books:
        if book["id"] == active_id:
            return book
    return None


def render_scene_actions() -> None:
    left, middle, right = st.columns([1, 1, 5])
    with left:
        if st.button("回门口"):
            go_to_scene("gate")
    with middle:
        if st.button("换地方"):
            go_to_scene("map")
    with right:
        st.caption("结束阅读时回到门口；想换一种阅读方式，就去公园里另一个地方。")


def render_gate_scene(books: list[dict]) -> None:
    render_park_visual(
        "gate",
        "公园门口的书摊",
        "先挑一本今天要带进公园的书。",
    )

    if books:
        options = {book_label(book): book["id"] for book in books}
        selected_label = st.selectbox("今天带哪本书散步？", options=list(options.keys()))
        selected_book = find_book(options[selected_label])
        st.markdown(
            f"""
            <div class="coach-note">
            你的阅读目的：{selected_book.get('purpose') or '还没有填写。可以先读，之后再补。'}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("带着这本书进公园", type="primary"):
            set_active_book(selected_book["id"])
            go_to_scene("map")
    else:
        st.info("书摊还是空的。先新建一本书，再开始这段阅读散步。")

    with st.expander("在书摊登记一本新书", expanded=not bool(books)):
        with st.form("park_new_book_form", clear_on_submit=True):
            title = st.text_input("书名")
            author = st.text_input("作者")
            purpose = st.text_area(
                "阅读目的",
                placeholder="例如：我想理解这本书的核心思想，并把它用到自己的工作和生活里。",
                height=100,
            )
            submitted = st.form_submit_button("保存并带进公园")

        if submitted:
            if not title.strip():
                st.warning("请先填写书名。")
            else:
                book = add_book(title=title, author=author, purpose=purpose)
                set_active_book(book["id"])
                st.success(f"已保存：《{book['title']}》")
                go_to_scene("map")


def render_scene_picker(selected_book: dict) -> None:
    render_park_visual(
        "map",
        "公园里的岔路",
        "选择一个地方，决定这次阅读怎么展开。",
        selected_book["title"],
    )
    render_scene_actions()

    scene_columns = st.columns(4)
    for index, scene in enumerate(PARK_SCENES):
        with scene_columns[index]:
            st.markdown(
                f"""
                <div class="scene-card">
                    <strong>{scene['name']}</strong>
                    <span>{scene['subtitle']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(scene["button"], key=f"park_scene_{scene['id']}"):
                go_to_scene(scene["id"])


def render_source_scene(selected_book: dict) -> None:
    render_park_visual(
        "pavilion",
        "资料小亭",
        "把书放进资料库，后面的对话就能尽量基于原文。",
        selected_book["title"],
    )
    render_scene_actions()

    source = get_book_source(selected_book["id"])
    if source:
        st.success(
            f"已上传资料：{source['filename']}，约 {source['char_count']} 个字符，"
            f"更新时间：{source['updated_at']}"
        )
        with st.expander("预览资料开头", expanded=False):
            st.write(source["text"][:2000])
    else:
        st.info("这本书还没有上传资料。上传后，陪读对话会优先检索这里的内容。")

    uploaded_file = st.file_uploader(
        "上传 txt、md、pdf、epub 或 mobi",
        type=["txt", "md", "pdf", "epub", "mobi"],
        help="上传后会抽取成纯文本，用作这本书的资料库。",
        key=f"park_source_upload_{selected_book['id']}",
    )
    if uploaded_file and st.button("保存为这本书的资料", type="primary"):
        try:
            with st.spinner("正在抽取并保存资料..."):
                source_text = extract_text_from_upload(uploaded_file)
                if not source_text.strip():
                    st.warning("没有从文件中抽取到文字。")
                else:
                    meta = save_book_source(
                        selected_book["id"],
                        uploaded_file,
                        source_text,
                    )
                    st.success(
                        f"资料已保存：{meta['filename']}，约 {meta['char_count']} 个字符。"
                    )
                    st.rerun()
        except Exception as exc:
            st.error(f"资料保存失败：{exc}")


def render_record_scene(
    selected_book: dict,
    api_key: str,
    model: str,
    api_base_url: str,
) -> None:
    render_park_visual(
        "table",
        "草地书桌",
        "把今天读到的章节、书摘和困惑记下来。",
        selected_book["title"],
    )
    render_scene_actions()

    with st.form("park_reading_form"):
        chapter = st.text_input("章节")
        today_goal = st.text_area("今日目标", height=80)
        excerpt = st.text_area("书摘", height=180)
        confusion = st.text_area("我的困惑", height=140)
        submitted = st.form_submit_button("生成陪读反馈并保存")

    if submitted:
        if not chapter.strip():
            st.warning("请填写章节，方便后续整理笔记。")
        elif not excerpt.strip() and not confusion.strip():
            st.warning("至少填写一些书摘或困惑，Agent 才能陪你读。")
        else:
            with st.spinner("正在生成陪读反馈..."):
                feedback = generate_feedback(
                    book=selected_book,
                    chapter=chapter,
                    today_goal=today_goal,
                    excerpt=excerpt,
                    confusion=confusion,
                    prompt_path=PROMPT_PATH,
                    api_key=api_key,
                    model=model,
                    api_base_url=api_base_url,
                )

            record = add_reading_record(
                book_id=selected_book["id"],
                chapter=chapter,
                today_goal=today_goal,
                excerpt=excerpt,
                confusion=confusion,
                feedback=feedback,
            )

            st.success("已生成并保存本次阅读记录。")
            st.markdown(f"### 本次陪读反馈：{record['chapter']}")
            render_feedback(feedback)


def render_chat_scene(
    selected_book: dict,
    api_key: str,
    model: str,
    api_base_url: str,
    model_ready: bool,
) -> None:
    render_park_visual(
        "bench",
        "林荫长椅",
        "像散步聊天一样，把书里的问题慢慢讲开。",
        selected_book["title"],
    )
    render_scene_actions()

    source = get_book_source(selected_book["id"])
    source_text = source["text"] if source else ""
    messages = get_chat_messages(selected_book["id"])
    selected_records = get_records(selected_book["id"])
    active_session = get_reading_session(selected_book["id"])

    left, right = st.columns([2, 1])
    with left:
        st.markdown(
            f"""
            <div class="coach-note">
            当前对话会保存在《{selected_book['title']}》下面。你可以把它当作阅读记录的延伸，而不是一次性聊天。
            </div>
            """,
            unsafe_allow_html=True,
        )
        chat_mode = st.selectbox(
            "今天想让谁陪你读？",
            CHAT_MODES,
            key=f"park_chat_mode_{selected_book['id']}",
        )
        st.caption(MODE_HINTS[chat_mode])
        live_context = st.text_area(
            "当前正在读的段落或你的临时想法（可选）",
            placeholder="可以贴一小段原文、你的理解、或者刚刚卡住的地方。",
            height=120,
            key=f"park_live_context_{selected_book['id']}",
        )
    with right:
        st.markdown("**这本书的陪读状态**")
        render_book_status(len(selected_records), len(messages), bool(source))
        if selected_records:
            latest = selected_records[-1]
            st.caption(f"最近读到：{latest.get('chapter') or '未填写章节'}")

        st.markdown("**本次阅读**")
        if active_session:
            duration_text, _ = session_elapsed(active_session)
            session_message_count = max(len(messages) - int(active_session.get("message_count", 0)), 0)
            st.metric("已阅读", duration_text)
            st.caption(f"本次已产生 {session_message_count} 条对话消息。")
            if st.button("结束阅读并保存到回忆步道", type="primary"):
                record = save_reading_session_as_record(selected_book, messages)
                if record:
                    st.success("已保存为一条完整的阅读记录。")
                    go_to_scene("trail")
                else:
                    st.warning("还没有正在进行的阅读。")
        else:
            st.caption("点击开始后，我会记录这次阅读的时长，并在结束时把整轮对话合并成一条阅读记录。")
            if st.button("开始阅读计时", type="primary"):
                start_reading_session(selected_book["id"], len(messages))
                st.rerun()

        with st.expander("对话管理", expanded=False):
            st.caption("对话默认会保存。只有你主动点击下面按钮时才会清空。")
            if st.button("清空这本书的对话", type="secondary"):
                clear_book_chat(selected_book["id"])
                clear_reading_session(selected_book["id"])
                st.rerun()

    with st.expander("看看最近阅读记录给对话的上下文", expanded=False):
        if not selected_records:
            st.write("这本书还没有阅读记录。你仍然可以先聊天，之后再补记录。")
        else:
            for record in selected_records[-3:][::-1]:
                st.markdown(f"**{record.get('chapter') or '未填写章节'}**")
                st.write(record.get("confusion") or record.get("excerpt") or "没有摘录内容")

    with st.expander("看看资料库会检索什么", expanded=False):
        if not source:
            st.write("这本书还没有上传资料。")
        else:
            preview_query = live_context or "核心观点"
            snippets = retrieve_relevant_snippets(source_text, preview_query)
            st.write(snippets or "还没有可展示的检索片段。")

    st.markdown("**可以这样开口**")
    quick_cols = st.columns(3)
    quick_message = None
    for index, prompt in enumerate(QUICK_PROMPTS):
        with quick_cols[index % 3]:
            if st.button(
                prompt,
                key=f"park_quick_{selected_book['id']}_{index}",
                disabled=not model_ready,
            ):
                quick_message = prompt

    if not model_ready:
        st.warning("请先在左侧填写 API Base URL、API Key 和模型名，再开始陪读对话。")

    if not messages:
        with st.chat_message("assistant"):
            st.markdown(
                f"我在。我们今天就围绕《{selected_book['title']}》慢慢读。"
                "你可以贴一段原文，也可以直接说哪里没懂；我会先帮你讲明白，"
                "再追问你一个不太累的问题。"
            )

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_message = st.chat_input(
        "像聊天一样问：我这样理解对吗？这段怎么用？",
        disabled=not model_ready,
    )
    next_message = quick_message or user_message
    if next_message:
        handle_chat_turn(
            selected_book=selected_book,
            messages=messages,
            user_message=next_message,
            mode=chat_mode,
            live_context=live_context,
            api_key=api_key,
            model=model,
            api_base_url=api_base_url,
            source_text=source_text,
        )


def render_trail_scene(selected_book: dict) -> None:
    render_park_visual(
        "trail",
        "回忆步道",
        "回看一路留下的记录、对话和可以带走的笔记。",
        selected_book["title"],
    )
    render_scene_actions()

    selected_records = get_records(selected_book["id"])
    messages = get_chat_messages(selected_book["id"])

    export_col, status_col = st.columns([1, 2])
    with export_col:
        if CLOUD_MODE:
            markdown = build_book_markdown(selected_book, selected_records, messages)
            st.download_button(
                "下载这本书的 Markdown 笔记",
                data=markdown,
                file_name=f"{selected_book['title']}_reading_notes.md",
                mime="text/markdown",
            )
        elif st.button("导出这本书的 Markdown 笔记"):
            exported_path = local_export_book_markdown(selected_book["id"])
            st.success("导出完成。")
            st.code(str(exported_path), language="text")
    with status_col:
        render_book_status(len(selected_records), len(messages), bool(get_book_source(selected_book["id"])))

    st.markdown("### 阅读记录")
    if not selected_records:
        st.caption("还没有正式阅读记录。可以先去草地书桌记录一次，或在长椅把对话沉淀成记录。")
    for item in sorted(selected_records, key=lambda row: row["created_at"], reverse=True):
        with st.expander(f"{item['chapter']}｜{item['created_at']}"):
            st.markdown("**今日目标**")
            st.write(item.get("today_goal") or "未填写")
            st.markdown("**书摘 / 对话问题**")
            st.write(item.get("excerpt") or "未填写")
            st.markdown("**我的困惑**")
            st.write(item.get("confusion") or "未填写")
            st.markdown("**陪读反馈**")
            render_feedback(item.get("feedback", ""))

    st.markdown("### 陪读会话")
    st.caption("陪读对话不再按单条消息展示。点击“结束阅读并保存到回忆步道”后，会作为一整次阅读记录出现在上方。")


def render_park_app(
    api_key: str,
    model: str,
    api_base_url: str,
    model_ready: bool,
) -> None:
    books = get_books()
    selected_book = get_active_book(books)
    scene = st.session_state.get("park_scene", "gate")

    if not selected_book and scene != "gate":
        scene = "gate"
        st.session_state["park_scene"] = "gate"

    if scene == "gate":
        render_gate_scene(books)
    elif scene == "map" and selected_book:
        render_scene_picker(selected_book)
    elif scene == "bench" and selected_book:
        render_chat_scene(selected_book, api_key, model, api_base_url, model_ready)
    elif scene == "table" and selected_book:
        render_record_scene(selected_book, api_key, model, api_base_url)
    elif scene == "pavilion" and selected_book:
        render_source_scene(selected_book)
    elif scene == "trail" and selected_book:
        render_trail_scene(selected_book)
    else:
        st.session_state["park_scene"] = "gate"
        st.rerun()


def handle_chat_turn(
    selected_book: dict,
    messages: list[dict],
    user_message: str,
    mode: str,
    live_context: str,
    api_key: str,
    model: str,
    api_base_url: str,
    source_text: str,
) -> None:
    add_chat_message(selected_book["id"], "user", user_message)

    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        try:
            with st.spinner("我在想怎么接住这个问题..."):
                source_query = "\n".join([user_message, live_context])
                source_snippets = retrieve_relevant_snippets(source_text, source_query)
                reply = generate_chat_reply(
                    book=selected_book,
                    records=get_records(),
                    messages=messages,
                    user_message=user_message,
                    prompt_path=PROMPT_PATH,
                    api_key=api_key,
                    model=model,
                    api_base_url=api_base_url,
                    mode=mode,
                    live_context=live_context,
                    source_snippets=source_snippets,
                )
        except Exception as exc:
            st.error(str(exc))
            return
        st.markdown(reply)

    add_chat_message(selected_book["id"], "assistant", reply)
    st.rerun()


render_app_intro()

with st.sidebar:
    if CLOUD_MODE:
        st.header("我的账号")
        st.caption(current_user.get("email", "已登录"))
        if st.button("退出登录"):
            try:
                cloud_client.sign_out()
            finally:
                st.session_state.pop("supabase_access_token", None)
                st.session_state.pop("supabase_user", None)
                st.rerun()

        st.divider()

    st.header("模型接入")
    st.caption("填写 OpenAI-compatible API 后，陪读对话会直接调用真实模型。")
    api_base_url = st.text_input(
        "API Base URL",
        value=os.getenv("OPENAI_BASE_URL", ""),
        help="例如：https://api.openai.com/v1，或其他兼容 /chat/completions 的地址。",
    )
    api_key = st.text_input(
        "API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
    )
    model = st.text_input(
        "模型名",
        value=os.getenv("OPENAI_MODEL", ""),
    )
    model_ready = bool(api_base_url.strip() and api_key.strip() and model.strip())
    if model_ready:
        st.info("模型配置已填写，建议先测试连接。")
    else:
        st.info("陪读对话需要填写完整模型配置。阅读记录仍可使用本地模板。")

    if st.button("测试模型连接"):
        try:
            with st.spinner("正在测试模型连接..."):
                test_reply = test_model_connection(
                    api_base_url=api_base_url,
                    api_key=api_key,
                    model=model,
                )
            st.success(f"模型连接成功：{test_reply[:80]}")
        except Exception as exc:
            st.error(f"模型连接失败：{exc}")

books = get_books()
records = get_records()

render_park_app(
    api_key=api_key,
    model=model,
    api_base_url=api_base_url,
    model_ready=model_ready,
)
st.stop()

tab_new_book, tab_source, tab_read, tab_chat, tab_history, tab_export = st.tabs(
    ["新建书籍", "资料库", "阅读记录", "陪读对话", "阅读时间线", "导出笔记"]
)

with tab_new_book:
    st.subheader("新建一本书")
    with st.form("new_book_form", clear_on_submit=True):
        title = st.text_input("书名")
        author = st.text_input("作者")
        purpose = st.text_area(
            "阅读目的",
            placeholder="例如：我想理解这本书的核心思想，并把它用到自己的工作和生活里。",
            height=120,
        )
        submitted = st.form_submit_button("保存书籍")

    if submitted:
        if not title.strip():
            st.warning("请先填写书名。")
        else:
            book = add_book(title=title, author=author, purpose=purpose)
            st.success(f"已保存：《{book['title']}》")

with tab_read:
    st.subheader("记录一次阅读")
    books = get_books()

    if not books:
        st.info("请先在“新建一本书”里添加一本书。")
    else:
        options = {book_label(book): book["id"] for book in books}
        selected_label = st.selectbox("选择书籍", options=list(options.keys()))
        selected_book = find_book(options[selected_label])

        with st.form("reading_form"):
            chapter = st.text_input("章节")
            today_goal = st.text_area("今日目标", height=80)
            excerpt = st.text_area("书摘", height=180)
            confusion = st.text_area("我的困惑", height=140)
            submitted = st.form_submit_button("生成陪读反馈并保存")

        if submitted:
            if not chapter.strip():
                st.warning("请填写章节，方便后续整理笔记。")
            elif not excerpt.strip() and not confusion.strip():
                st.warning("至少填写一些书摘或困惑，Agent 才能陪你读。")
            else:
                with st.spinner("正在生成陪读反馈..."):
                    feedback = generate_feedback(
                        book=selected_book,
                        chapter=chapter,
                        today_goal=today_goal,
                        excerpt=excerpt,
                        confusion=confusion,
                        prompt_path=PROMPT_PATH,
                        api_key=api_key,
                        model=model,
                        api_base_url=api_base_url,
                    )

                record = add_reading_record(
                    book_id=selected_book["id"],
                    chapter=chapter,
                    today_goal=today_goal,
                    excerpt=excerpt,
                    confusion=confusion,
                    feedback=feedback,
                )

                st.success("已生成并保存本次阅读记录。")
                st.markdown(f"### 本次陪读反馈：{record['chapter']}")
                render_feedback(feedback)

with tab_source:
    st.subheader("书籍资料库")
    books = get_books()

    if not books:
        st.info("请先在“新建一本书”里添加一本书。")
    else:
        options = {book_label(book): book["id"] for book in books}
        selected_label = st.selectbox("选择书籍", options=list(options.keys()), key="source_book")
        selected_book = find_book(options[selected_label])
        source = get_book_source(selected_book["id"])

        if source:
            st.success(
                f"已上传资料：{source['filename']}，约 {source['char_count']} 个字符，"
                f"更新时间：{source['updated_at']}"
            )
            with st.expander("预览资料开头", expanded=False):
                st.write(source["text"][:2000])
        else:
            st.info("这本书还没有上传资料。")

        uploaded_file = st.file_uploader(
            "上传 txt、md、pdf、epub 或 mobi",
            type=["txt", "md", "pdf", "epub", "mobi"],
            help="上传后会抽取成纯文本，用作这本书的资料库。",
        )
        if uploaded_file and st.button("保存为这本书的资料"):
            try:
                with st.spinner("正在抽取并保存资料..."):
                    source_text = extract_text_from_upload(uploaded_file)
                    if not source_text.strip():
                        st.warning("没有从文件中抽取到文字。")
                    else:
                        meta = save_book_source(
                            selected_book["id"],
                            uploaded_file,
                            source_text,
                        )
                        st.success(
                            f"资料已保存：{meta['filename']}，约 {meta['char_count']} 个字符。"
                        )
                        st.rerun()
            except Exception as exc:
                st.error(f"资料保存失败：{exc}")

with tab_chat:
    st.subheader("陪读对话")
    books = get_books()

    if not books:
        st.info("请先在“新建书籍”里添加一本书。")
    else:
        options = {book_label(book): book["id"] for book in books}
        selected_label = st.selectbox("对话书籍", options=list(options.keys()))
        selected_book = find_book(options[selected_label])
        source = get_book_source(selected_book["id"])
        source_text = source["text"] if source else ""
        messages = get_chat_messages(selected_book["id"])
        selected_records = [
            record for record in get_records()
            if record["book_id"] == selected_book["id"]
        ]

        left, right = st.columns([2, 1])
        with left:
            st.markdown(
                f"""
                <div class="coach-note">
                当前对话会保存在《{selected_book['title']}》下面。你可以把它当作阅读记录的延伸，而不是一次性聊天。
                </div>
                """,
                unsafe_allow_html=True,
            )
            chat_mode = st.selectbox(
                "今天想让谁陪你读？",
                CHAT_MODES,
            )
            st.caption(MODE_HINTS[chat_mode])
            live_context = st.text_area(
                "当前正在读的段落或你的临时想法（可选）",
                placeholder="可以贴一小段原文、你的理解、或者刚刚卡住的地方。",
                height=120,
            )
        with right:
            st.markdown("**这本书的陪读状态**")
            render_book_status(len(selected_records), len(messages), bool(source))
            if selected_records:
                latest = selected_records[-1]
                st.caption(f"最近读到：{latest.get('chapter') or '未填写章节'}")
            if messages:
                if st.button("把最近对话沉淀成阅读记录", type="primary"):
                    if save_latest_dialogue_as_record(selected_book["id"], messages):
                        st.success("已保存为一条新的阅读记录。")
                        st.rerun()
                    else:
                        st.warning("还没有完整的一问一答可以沉淀。")
            with st.expander("对话管理", expanded=False):
                st.caption("对话默认会保存。只有你主动点击下面按钮时才会清空。")
                if st.button("清空这本书的对话", type="secondary"):
                    clear_book_chat(selected_book["id"])
                    st.rerun()

        with st.expander("看看最近阅读记录给对话的上下文", expanded=False):
            if not selected_records:
                st.write("这本书还没有阅读记录。你仍然可以先聊天，之后再补记录。")
            else:
                for record in selected_records[-3:][::-1]:
                    st.markdown(f"**{record.get('chapter') or '未填写章节'}**")
                    st.write(record.get("confusion") or record.get("excerpt") or "没有摘录内容")

        with st.expander("看看资料库会检索什么", expanded=False):
            if not source:
                st.write("这本书还没有上传资料。")
            else:
                preview_query = live_context or "核心观点"
                snippets = retrieve_relevant_snippets(source_text, preview_query)
                st.write(snippets or "还没有可展示的检索片段。")

        st.markdown("**可以这样开口**")
        quick_cols = st.columns(3)
        quick_message = None
        for index, prompt in enumerate(QUICK_PROMPTS):
            with quick_cols[index % 3]:
                if st.button(
                    prompt,
                    key=f"quick_{selected_book['id']}_{index}",
                    disabled=not model_ready,
                ):
                    quick_message = prompt

        if not model_ready:
            st.warning("请先在左侧填写 API Base URL、API Key 和模型名，再开始陪读对话。")

        if not messages:
            with st.chat_message("assistant"):
                st.markdown(
                    f"我在。我们今天就围绕《{selected_book['title']}》慢慢读。"
                    "你可以贴一段原文，也可以直接说哪里没懂；我会先帮你讲明白，"
                    "再追问你一个不太累的问题。"
                )

        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_message = st.chat_input(
            "像聊天一样问：我这样理解对吗？这段怎么用？",
            disabled=not model_ready,
        )
        next_message = quick_message or user_message
        if next_message:
            handle_chat_turn(
                selected_book=selected_book,
                messages=messages,
                user_message=next_message,
                mode=chat_mode,
                live_context=live_context,
                api_key=api_key,
                model=model,
                api_base_url=api_base_url,
                source_text=source_text,
            )

with tab_history:
    st.subheader("阅读时间线")
    books = get_books()
    records = get_records()

    if not books:
        st.info("还没有书籍。")
    else:
        book_map = {book["id"]: book for book in books}
        book_names = ["全部"] + [book_label(book) for book in books]
        selected = st.selectbox("筛选书籍", book_names)

        if selected == "全部":
            visible_records = records
            visible_book_ids = [book["id"] for book in books]
        else:
            selected_id = {book_label(book): book["id"] for book in books}[selected]
            visible_records = [item for item in records if item["book_id"] == selected_id]
            visible_book_ids = [selected_id]

        visible_messages = []
        for book_id in visible_book_ids:
            visible_messages.extend(get_chat_messages(book_id))

        if not visible_records and not visible_messages:
            st.info("这本书还没有阅读记录或陪读对话。")
        else:
            st.markdown("### 阅读记录")
            if not visible_records:
                st.caption("还没有正式阅读记录。你可以在陪读对话里把最近一轮对话沉淀成记录。")
            for item in sorted(visible_records, key=lambda row: row["created_at"], reverse=True):
                book = book_map.get(item["book_id"], {"title": "未知书籍", "author": ""})
                with st.expander(f"{book['title']}｜{item['chapter']}｜{item['created_at']}"):
                    st.markdown("**今日目标**")
                    st.write(item.get("today_goal") or "未填写")
                    st.markdown("**书摘 / 对话问题**")
                    st.write(item.get("excerpt") or "未填写")
                    st.markdown("**我的困惑**")
                    st.write(item.get("confusion") or "未填写")
                    st.markdown("**陪读反馈**")
                    render_feedback(item.get("feedback", ""))

            st.markdown("### 陪读对话")
            if not visible_messages:
                st.caption("还没有保存的陪读对话。")
            else:
                for message in sorted(
                    visible_messages,
                    key=lambda row: row.get("created_at", ""),
                    reverse=True,
                )[:40]:
                    book = book_map.get(message["book_id"], {"title": "未知书籍", "author": ""})
                    role_name = "我" if message["role"] == "user" else "读书教练"
                    with st.expander(
                        f"{book['title']}｜{role_name}｜{message.get('created_at', '')}"
                    ):
                        st.markdown(message.get("content") or "")

with tab_export:
    st.subheader("按书名导出 Markdown 笔记")
    books = get_books()

    if not books:
        st.info("请先添加书籍。")
    else:
        options = {book_label(book): book["id"] for book in books}
        selected_label = st.selectbox("选择要导出的书", options=list(options.keys()))
        selected_book = find_book(options[selected_label])

        if CLOUD_MODE:
            markdown = build_book_markdown(
                selected_book,
                get_records(selected_book["id"]),
                get_chat_messages(selected_book["id"]),
            )
            st.download_button(
                "下载 Markdown",
                data=markdown,
                file_name=f"{selected_book['title']}_reading_notes.md",
                mime="text/markdown",
            )
        elif st.button("导出 Markdown"):
            exported_path = local_export_book_markdown(selected_book["id"])
            st.success("导出完成。")
            st.code(str(exported_path), language="text")
