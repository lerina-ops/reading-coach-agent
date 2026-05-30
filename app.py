import os
import importlib
from pathlib import Path

import streamlit as st

import reading_coach.coach as coach_module
from reading_coach.library import extract_text_from_upload, retrieve_relevant_snippets
from reading_coach.storage import (
    add_book,
    add_chat_message,
    add_reading_record,
    clear_book_chat,
    export_book_markdown,
    find_book,
    get_book_source,
    get_books,
    get_chat_messages,
    get_records,
    save_book_source,
)


coach_module = importlib.reload(coach_module)
generate_feedback = coach_module.generate_feedback
generate_chat_reply = coach_module.generate_chat_reply
test_model_connection = coach_module.test_model_connection


BASE_DIR = Path(__file__).parent
PROMPT_PATH = BASE_DIR / "prompts" / "reading_coach.md"
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
    st.header("模型接入")
    st.caption("填写 OpenAI-compatible API 后，陪读对话会直接调用真实模型。")
    api_base_url = st.text_input(
        "API Base URL",
        value=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        help="例如：https://api.openai.com/v1，或其他兼容 /chat/completions 的地址。",
    )
    api_key = st.text_input(
        "API Key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
    )
    model = st.text_input(
        "模型名",
        value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
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
            "上传 txt、md 或 pdf",
            type=["txt", "md", "pdf"],
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
                            uploaded_file.name,
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

        if st.button("导出 Markdown"):
            selected_book = find_book(options[selected_label])
            exported_path = export_book_markdown(selected_book["id"])
            st.success("导出完成。")
            st.code(str(exported_path), language="text")
