import json
import base64
import io
import re
import os
import streamlit as st
import groq

# ---------- 将背景图片转换为 Base64 嵌入 CSS ----------
def get_base64_of_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return None

bg_base64 = get_base64_of_image("background.jpg")
if bg_base64 is None:
    st.warning("Background image not found. Using solid light background.")
    bg_css = "background-color: #f0f0f0;"
else:
    bg_css = f"background-image: url('data:image/jpeg;base64,{bg_base64}');"

# Page config
st.set_page_config(layout="wide", page_title="Chinese Learning Assistant")

# ---------- 加载所有 Level 数据 ----------
@st.cache_data
def load_level_data():
    levels = {}
    for i in range(1, 4):
        try:
            with open(f"level{i}.json", "r", encoding="utf-8") as f:
                levels[f"Level {i}"] = json.load(f)
        except FileNotFoundError:
            st.error(f"level{i}.json not found. Please ensure all level files exist.")
            st.stop()
    return levels

levels_data = load_level_data()

# ---------- Groq 客户端 ----------
client = groq.Client(api_key=os.environ.get("GROQ_API_KEY") or st.secrets["GROQ_API_KEY"])

# ---------- 语音转文字（Whisper）----------
def transcribe_audio(audio_bytes):
    try:
        transcription = client.audio.transcriptions.create(
            file=("audio.wav", audio_bytes, "audio/wav"),
            model="whisper-large-v3",
        )
        return transcription.text
    except Exception as e:
        return f"[转录失败: {e}]"

# ---------- 判断文本是否含中文 ----------
def has_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

# ---------- 文字转语音 ----------
def text_to_speech(text):
    try:
        if has_chinese(text):
            # 中文用 gTTS
            from gtts import gTTS
            tts = gTTS(text=text, lang="zh")
            buf = io.BytesIO()
            tts.write_to_fp(buf)
            buf.seek(0)
            return buf, "audio/mp3"
        else:
            # 英文用 Groq Orpheus
            response = client.audio.speech.create(
                model="canopylabs/orpheus-v1-english",
                voice="autumn",
                input=text,
                response_format="wav",
            )
            buf = io.BytesIO(response.read())
            buf.seek(0)
            return buf, "audio/wav"
    except Exception as e:
        st.error(f"TTS 失败: {e}")
        return None, None

# ---------- 构建系统提示（包含所有词汇和例句）----------
def build_system_prompt(levels):
    prompt = "You are a Chinese learning assistant. Below is the outline of the learning content (Levels 1-3). The user may ask about specific items, but detailed vocabulary and examples are not listed here to save tokens. Please answer based on your knowledge, but if needed, you can ask the user to provide more details and make your answer structured, do not give messy information.\n\n"
    
    def extract_outline(node, indent=0):
        outline = ""
        if isinstance(node, dict):
            if "name" in node and node["name"]:
                outline += "  " * indent + "- " + node["name"] + "\n"
            for key, val in node.items():
                if key not in ["name", "notes", "examples", "vocabulary"]:
                    outline += extract_outline(val, indent + 1)
        return outline

    for level_name, data in levels.items():
        prompt += f"=== {level_name} ===\n"
        prompt += extract_outline(data)
        prompt += "\n"
    
    prompt += "Answer the user's questions based on this outline. If you need specific vocabulary or example sentences, ask the user to provide them."
    return prompt

system_prompt = build_system_prompt(levels_data)

# ---------- 初始化聊天记录 ----------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": system_prompt}
    ]

# ---------- 初始化导航状态 ----------
if "level" not in st.session_state:
    st.session_state.level = None
if "path" not in st.session_state:
    st.session_state.path = []
if "chat_open" not in st.session_state:
    st.session_state.chat_open = False
if "pending_audio_reply" not in st.session_state:
    st.session_state.pending_audio_reply = None

# ---------- 自定义CSS ----------
st.markdown(f"""
<style>
    /* 导入Google字体 Manrope */
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&display=swap');

    /* 背景图片设置 */
    body {{
        {bg_css}
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        background-repeat: no-repeat;
        background-color: #f0f0f0;
    }}

    /* 所有容器背景透明 */
    html, body, .stApp, .main, div[data-testid="stAppViewContainer"], 
    div[data-testid="stHeader"], div[data-testid="stToolbar"],
    div[data-testid="stVerticalBlock"], div[data-testid="column"],
    header, footer {{
        background-color: transparent !important;
    }}

    /* 隐藏Streamlit默认footer */
    #stFooter {{
        display: none !important;
    }}

    .main {{
        padding: 2rem 1rem !important;
    }}

    /* 所有文字颜色纯黑，无阴影 */
    html, body, [class*="css"], h1, h2, h3, p, div, span, .stMarkdown {{
        color: #000000 !important;
        text-shadow: none !important;
    }}

    /* 主标题：大写加粗纯黑 */
    h1 {{
        font-size: 72px !important;
        font-weight: 800 !important;
        letter-spacing: -0.5px;
        color: #000000 !important;
        margin-bottom: 16px !important;
        text-transform: uppercase;
    }}

    h2 {{
        font-size: 54px !important;
        font-weight: 400 !important;
        color: #000000 !important;
        margin: 24px 0 8px 0 !important;
    }}

    h3 {{
        font-size: 42px !important;
        font-weight: 500 !important;
        color: #000000 !important;
        margin: 16px 0 8px 0 !important;
    }}

    /* ---------- 模仿项目标题的 Level 按钮样式 ---------- */
    div[data-testid="column"] .stButton > button {{
        font-size: 56px !important;
        font-weight: 700 !important;
        background-color: transparent !important;
        color: #000000 !important;
        border: none !important;
        box-shadow: none !important;
        padding: 8px 0 !important;
        border-radius: 0 !important;
        transition: all 0.2s ease !important;
        width: 100%;
        text-align: left;
        margin: 0 !important;
        line-height: 1.2;
    }}
    div[data-testid="column"] .stButton > button:hover {{
        text-decoration: underline !important;
        background-color: transparent !important;
    }}

    /* 其他按钮（目录按钮）保持原有透明样式 */
    .stButton > button {{
        font-size: 28px !important;
        font-weight: 500 !important;
        padding: 20px 24px !important;
        border-radius: 40px !important;
        background-color: transparent !important;
        color: #000000 !important;
        border: 2px solid rgba(0,0,0,0.3) !important;
        transition: all 0.2s ease !important;
        width: 100%;
        box-shadow: none !important;
    }}

    .stButton > button:hover {{
        background-color: rgba(255,255,255,0.3) !important;
        border-color: #000000 !important;
    }}

    /* 所有内容卡片：半透明白色背景（不透明度0.6/），纯黑文字 */
    div[data-testid="stVerticalBlock"] > div {{
        background-color: rgba(255,255,255,0.4) !important;
        border: none !important;
        box-shadow: none !important;
        padding: 16px !important;
        border-radius: 16px !important;
    }}

    /* 词汇卡片内文字 */
    div[data-testid="stVerticalBlock"] > div h3 {{
        font-size: 48px !important;
        font-weight: 500 !important;
        color: #000000 !important;
        margin: 0 0 8px 0 !important;
    }}

    /* 拼音 */
    div[data-testid="stVerticalBlock"] > div div {{
        font-size: 32px !important;
        color: #333333 !important;
        margin-bottom: 8px !important;
    }}

    /* 例句、notes 文字 */
    div[data-testid="stVerticalBlock"] > div p {{
        font-size: 32px !important;
        color: #000000 !important;
    }}

    /* 面包屑导航 */
    .breadcrumb {{
        font-size: 28px !important;
        color: #333333 !important;
        padding: 12px 0;
        border-bottom: 2px solid rgba(0,0,0,0.2);
        margin-bottom: 24px;
        font-weight: 400;
    }}

    /* 返回按钮 */
    .back-button .stButton > button {{
        background-color: transparent !important;
        color: #000000 !important;
        border: none !important;
        padding: 12px 0 !important;
        font-size: 28px !important;
        text-align: left;
        font-weight: 500 !important;
        box-shadow: none !important;
        border-bottom: 2px solid transparent !important;
    }}

    .back-button .stButton > button:hover {{
        background-color: transparent !important;
        border-bottom: 2px solid #000000 !important;
    }}

    /* 列间距 */
    div[data-testid="column"] {{
        padding: 8px !important;
    }}

    hr {{
        margin: 24px 0 !important;
        border-color: rgba(0,0,0,0.1) !important;
    }}

    /* ---------- 悬浮聊天窗 ---------- */
    .chat-float-container {{
        position: fixed;
        bottom: 30px;
        right: 30px;
        z-index: 1000;
        display: flex;
        flex-direction: column;
        align-items: flex-end;
    }}

    .chat-toggle-btn {{
        width: 70px;
        height: 70px;
        border-radius: 50%;
        background-color: #ea4c89;
        border: none;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 600;
        color: white;
        margin-bottom: 10px;
        transition: transform 0.2s;
    }}

    .chat-toggle-btn:hover {{
        transform: scale(1.05);
    }}

    .chat-panel {{
        width: 420px;
        height: 600px;
        background-color: #ffffff !important;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        border: 1px solid rgba(0,0,0,0.1);
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }}

    .chat-messages-area {{
        flex: 1;
        overflow-y: auto;
        padding: 16px;
    }}

    .chat-input-area {{
        padding: 16px;
        border-top: 1px solid #e0e0e0;
    }}

    /* 聊天消息纯文本，无任何气泡或背景 */
    .chat-message {{
        margin-bottom: 12px;
        font-size: 28px;
        line-height: 1.4;
    }}

    .chat-message strong {{
        font-weight: 600;
        margin-right: 8px;
    }}

    /* 聊天输入框放大 */
    .stChatInput {{
        margin-top: 8px;
    }}
    .stChatInput > div {{
        background-color: transparent !important;
        border: 1px solid #dddddd !important;
        border-radius: 40px !important;
    }}
    .stChatInput input {{
        font-size: 32px !important;
        padding: 16px 24px !important;
        background-color: transparent !important;
        color: #000000 !important;
        min-height: 60px !important;
    }}
    .stChatInput input::placeholder {{
        font-size: 32px !important;
        color: #666666 !important;
    }}

    /* 清除聊天文本链接样式 */
    .clear-button-container .stButton > button {{
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #666666 !important;
        font-size: 24px !important;
        padding: 0 !important;
        margin: 0 !important;
        width: auto !important;
        text-decoration: underline !important;
        cursor: pointer;
        font-weight: 400 !important;
    }}
    .clear-button-container .stButton > button:hover {{
        color: #000000 !important;
    }}

    /* 音频播放器缩小 */
    .stAudio {{
        margin-top: 4px !important;
        margin-bottom: 4px !important;
    }}
    .stAudio audio {{
        height: 36px !important;
        width: 100% !important;
    }}

    /* 录音组件缩小 */
    div[data-testid="stAudioInput"] {{
        margin: 4px 0 !important;
    }}
</style>
""", unsafe_allow_html=True)

# ---------- 上半部分：导航和卡片显示 ----------
st.title("CHINESE LEARNING ASSISTANT")

col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Level 1", use_container_width=True):
        st.session_state.level = 1
        st.session_state.path = ["LEVEL_I"]
        st.rerun()
with col2:
    if st.button("Level 2", use_container_width=True):
        st.session_state.level = 2
        st.session_state.path = ["LEVEL_II"]
        st.rerun()
with col3:
    if st.button("Level 3", use_container_width=True):
        st.session_state.level = 3
        st.session_state.path = ["LEVEL_III"]
        st.rerun()

if st.session_state.level:
    data = levels_data[f"Level {st.session_state.level}"]
    current_node = data
    for key in st.session_state.path:
        current_node = current_node.get(key, {})
        if not current_node:
            st.error("Path error. Please go back.")
            st.stop()

    bread = " > ".join(st.session_state.path)
    st.markdown(f"<div class='breadcrumb'>{bread}</div>", unsafe_allow_html=True)

    if len(st.session_state.path) > 1:
        st.markdown("<div class='back-button'>", unsafe_allow_html=True)
        if st.button("Back", key="back_button"):
            st.session_state.path.pop()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    def display_node(node):
        if "name" in node:
            st.markdown(f"## {node['name']}")
        if "notes" in node and node["notes"]:
            with st.container(border=True):
                st.markdown(node["notes"])
        if "examples" in node and node["examples"]:
            st.markdown("### Example Sentences")
            cols = st.columns(3)
            for idx, ex in enumerate(node["examples"]):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"<div style='font-size:32px;'>{ex}</div>", unsafe_allow_html=True)
        if "vocabulary" in node and node["vocabulary"]:
            st.markdown("### Vocabulary")
            cols = st.columns(3)
            for idx, item in enumerate(node["vocabulary"]):
                with cols[idx % 3]:
                    parts = item.rsplit(" ", 1)
                    word = parts[0]
                    pinyin = parts[1] if len(parts) > 1 else ""
                    with st.container(border=True):
                        st.markdown(f"### {word}")
                        if pinyin:
                            st.markdown(f"<div>{pinyin}</div>", unsafe_allow_html=True)
        if not any(key in node for key in ["notes", "examples", "vocabulary"]):
            sub_keys = [k for k in node.keys() if k not in ("name", "notes", "examples", "vocabulary")]
            if not sub_keys:
                st.info("This section has no content to display.")
            else:
                cols = st.columns(3)
                for i, key in enumerate(sub_keys):
                    with cols[i % 3]:
                        if isinstance(node[key], dict) and "name" in node[key]:
                            label = node[key]["name"]
                        else:
                            label = key
                        if st.button(label, key=f"dir_{key}", use_container_width=True):
                            st.session_state.path.append(key)
                            st.rerun()

    display_node(current_node)

# ---------- 悬浮聊天窗 ----------
with st.container():
    st.markdown('<div class="chat-float-container">', unsafe_allow_html=True)

    if st.button("AI", key="chat_toggle_btn"):
        st.session_state.chat_open = not st.session_state.chat_open
        st.rerun()

    if st.session_state.chat_open:
        st.markdown('<div class="chat-panel">', unsafe_allow_html=True)

        # 顶部：Clear 按钮
        st.markdown('<div class="clear-button-container" style="display: flex; justify-content: flex-end; padding: 8px 16px 0;">', unsafe_allow_html=True)
        if st.button("Clear", key="clear_chat"):
            st.session_state.messages = [msg for msg in st.session_state.messages if msg["role"] == "system"]
            st.session_state.pending_audio_reply = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # 聊天消息区域
        st.markdown('<div class="chat-messages-area">', unsafe_allow_html=True)
        for i, msg in enumerate(st.session_state.messages):
            if msg["role"] != "system":
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-message"><strong>You:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-message"><strong>AI:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
                    # 🔊 朗读按钮
                    if st.button("🔊", key=f"tts_{i}"):
                        audio_buf, fmt = text_to_speech(msg["content"])
                        if audio_buf:
                            st.audio(audio_buf, format=fmt, autoplay=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 如果有待播放的 AI 回复音频，自动播放
        if st.session_state.pending_audio_reply:
            st.audio(st.session_state.pending_audio_reply["buf"],
                     format=st.session_state.pending_audio_reply["fmt"],
                     autoplay=True)
            st.session_state.pending_audio_reply = None

        # 输入区域
        st.markdown('<div class="chat-input-area">', unsafe_allow_html=True)

        # 🎤 语音输入
        audio_input = st.audio_input("🎤 录音发送", key="voice_input", label_visibility="collapsed")

        if audio_input is not None:
            with st.spinner("转录中..."):
                transcript = transcribe_audio(audio_input.read())
            if transcript and not transcript.startswith("[转录失败"):
                st.session_state.messages.append({"role": "user", "content": transcript})
                with st.spinner("AI 思考中..."):
                    try:
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                            temperature=0.7,
                            max_tokens=500
                        )
                        reply = response.choices[0].message.content
                    except Exception as e:
                        reply = f"Error: {e}"
                st.session_state.messages.append({"role": "assistant", "content": reply})
                # 生成 TTS 并存储待播放
                audio_buf, fmt = text_to_speech(reply)
                if audio_buf:
                    st.session_state.pending_audio_reply = {"buf": audio_buf, "fmt": fmt}
                st.rerun()

        # 💬 文字输入
        if prompt := st.chat_input("Ask a question...", key="text_input"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.markdown(f'<div class="chat-message"><strong>You:</strong> {prompt}</div>', unsafe_allow_html=True)
            with st.spinner("Thinking..."):
                try:
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                        temperature=0.7,
                        max_tokens=500
                    )
                    reply = response.choices[0].message.content
                except Exception as e:
                    reply = f"Error: {e}"
            st.session_state.messages.append({"role": "assistant", "content": reply})
            # 生成 TTS 并存储待播放
            audio_buf, fmt = text_to_speech(reply)
            if audio_buf:
                st.session_state.pending_audio_reply = {"buf": audio_buf, "fmt": fmt}
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
