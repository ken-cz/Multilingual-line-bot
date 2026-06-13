import os
import re
from flask import Flask, request, abort
from dotenv import load_dotenv
from openai import OpenAI
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN と LINE_CHANNEL_SECRET を .env に設定してください。")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY を .env に設定してください。")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

client = OpenAI(api_key=OPENAI_API_KEY)

# LINEの1メッセージあたりの文字数上限（5000）。長文はこの単位で分割して送る。
LINE_MAX_CHARS = 5000

def split_text(text, limit=LINE_MAX_CHARS):
    """長いテキストをLINEの上限以内のチャンクに分割する。できるだけ改行で区切る。"""
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks

def detect_lang(text):
    """文字種で入力言語を判定する（日本語/韓国語/英語のいずれか）。"""
    if re.search(r"[\uac00-\ud7a3]", text):                       # ハングル → 韓国語
        return "ko"
    if re.search(r"[\u3040-\u30ff]", text):                       # ひらがな/カタカナ → 日本語
        return "ja"
    if re.search(r"[\u4e00-\u9fff]", text):                       # 漢字のみ → 日本語とみなす
        return "ja"
    return "en"                                                   # ラテン文字など → 英語

# 入力言語ごとの「翻訳先」2言語（タグ, 言語名）
TARGETS = {
    "ja": [("KO", "Korean"), ("EN", "English")],
    "ko": [("JA", "Japanese"), ("EN", "English")],
    "en": [("JA", "Japanese"), ("KO", "Korean")],
}

def translate_to(text, target_name):
    """text を target_name（例: "Korean"）の1言語だけに翻訳して返す。"""
    system_prompt = (
        f"You are a translator. Translate the user's entire message into {target_name}. "
        f"Output ONLY the {target_name} translation, with no labels, quotes, notes, or "
        "explanations. Translate everything completely no matter how long; never omit, "
        "summarize, or shorten. Preserve the original line breaks and paragraph structure. "
        "Keep punctuation and names natural."
    )
    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        max_tokens=8000,  # 長文でも途中で切れないよう十分な上限を確保
    )
    return (completion.choices[0].message.content or "").strip()

@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_text = (event.message.text or "").strip()
    if not user_text:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="テキストを送ってください。"))
        return

    try:
        targets = TARGETS[detect_lang(user_text)]
        # 翻訳先の言語ごとに個別に翻訳し、ラベルを付けて結合する
        parts = []
        for tag, name in targets:
            t = translate_to(user_text, name)
            parts.append(f"[{tag}] {t}" if t else f"[{tag}] （翻訳に失敗しました）")
        translated = "\n\n".join(parts).strip()
        if not translated:
            translated = "翻訳結果が空でした。もう一度お試しください。"

        # 長文はLINEの1メッセージ上限(5000文字)ごとに分割し、最大5通までまとめて返信
        messages = [TextSendMessage(text=chunk) for chunk in split_text(translated)[:5]]
        line_bot_api.reply_message(event.reply_token, messages)

    except Exception as e:
        print("翻訳エラー詳細:", e)   # ← ターミナルにエラー原因を出す
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="翻訳エラーが発生しました")
        )

@app.get("/")
def health():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
