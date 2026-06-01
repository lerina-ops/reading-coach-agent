import os
import importlib
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
    "像朋友一样聊",
    "帮我讲明白",
    "追问我",
    "举例子",
    "帮我复盘成笔记",
]
QUICK_PROMPTS = [
    "这段话是什么意思？",
    "给我举个生活例子",
    "你反问我一个问题",
    "我这样理解对吗？",
    "帮我整理成今天的笔记",
    "给我一个明天能做的小行动",
]


st.set_page_config(
    page_title="陪我读书的 Agent",
    page_icon="📚",
    layout="wide",
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
        st.markdown(reply)

    add_chat_message(selected_book["id"], "assistant", reply)
    st.rerun()


st.title("陪我读书的 Agent")
st.caption("一个本地保存记录、陪你理解和复盘的读书教练 MVP")

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
    if api_key.strip():
        st.info("已填写 API Key，建议先测试连接。")
    else:
        st.info("未填写 API Key 时，会使用本地模板兜底。")

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

tab_new_book, tab_source, tab_read, tab_chat, tab_history, tab_export = st.tabs(
    ["新建一本书", "书籍资料库", "记录一次阅读", "陪读对话", "历史记录", "导出 Markdown"]
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
            help="上传后会抽取成纯文本，保存在本地 data/book_sources 目录。",
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
        st.info("请先在“新建一本书”里添加一本书。")
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
            chat_mode = st.radio(
                "这轮想怎么聊？",
                CHAT_MODES,
                horizontal=True,
            )
            live_context = st.text_area(
                "当前正在读的段落或你的临时想法（可选）",
                placeholder="可以贴一小段原文、你的理解、或者刚刚卡住的地方。",
                height=120,
            )
        with right:
            st.markdown("**这本书的陪读状态**")
            st.write(f"阅读记录：{len(selected_records)} 条")
            st.write(f"对话消息：{len(messages)} 条")
            st.write(f"书籍资料：{'已上传' if source else '未上传'}")
            if selected_records:
                latest = selected_records[-1]
                st.caption(f"最近读到：{latest.get('chapter') or '未填写章节'}")
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

        st.markdown("**你可以这样开口**")
        quick_cols = st.columns(3)
        quick_message = None
        for index, prompt in enumerate(QUICK_PROMPTS):
            with quick_cols[index % 3]:
                if st.button(prompt, key=f"quick_{selected_book['id']}_{index}"):
                    quick_message = prompt

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

        user_message = st.chat_input("像聊天一样问：我这样理解对吗？这段怎么用？")
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
    st.subheader("历史阅读记录")
    books = get_books()
    records = get_records()

    if not records:
        st.info("还没有阅读记录。")
    else:
        book_map = {book["id"]: book for book in books}
        book_names = ["全部"] + [book_label(book) for book in books]
        selected = st.selectbox("筛选书籍", book_names)

        if selected == "全部":
            visible_records = records
        else:
            selected_id = {book_label(book): book["id"] for book in books}[selected]
            visible_records = [item for item in records if item["book_id"] == selected_id]

        for item in sorted(visible_records, key=lambda row: row["created_at"], reverse=True):
            book = book_map.get(item["book_id"], {"title": "未知书籍", "author": ""})
            with st.expander(f"{book['title']}｜{item['chapter']}｜{item['created_at']}"):
                st.markdown("**今日目标**")
                st.write(item.get("today_goal") or "未填写")
                st.markdown("**书摘**")
                st.write(item.get("excerpt") or "未填写")
                st.markdown("**我的困惑**")
                st.write(item.get("confusion") or "未填写")
                st.markdown("**陪读反馈**")
                render_feedback(item.get("feedback", ""))

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
