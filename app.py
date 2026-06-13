import os
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

SYSTEM_PROMPT = '''You are an accurate translator.
- Detect the input language.
- Translate the ENTIRE input text completely, no matter how long it is.
  Never omit, summarize, shorten, or truncate any part. Preserve the
  original line breaks and paragraph structure.
- If the input is Japanese, reply with the Korean translation followed by
  the English translation, formatted as:
[KO] <full Korean translation>
[EN] <full English translation>
- If the input is NOT Japanese, reply with the Japanese translation followed
  by the English translation, formatted as:
[JA] <full Japanese translation>
[EN] <full English translation>
- Do not add any explanations or extra commentary. Keep punctuation and names natural.'''

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
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.2,
            max_tokens=8000,  # 長文でも途中で切れないよう十分な上限を確保
        )
        translated = (completion.choices[0].message.content or "").strip()
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
