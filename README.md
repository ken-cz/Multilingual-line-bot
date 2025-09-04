
# LINE 翻訳Bot（日本語⇄英語・韓国語）

ユーザーがLINEで送るテキストを自動翻訳します：
- 入力が日本語 → 韓国語と英語に翻訳（2行で返答）
- 入力が日本語以外 → 日本語に翻訳（1行で返答）

## セットアップ（ローカル + ngrok）

1. このフォルダをPCに展開し、Python 3.9+ を用意します。
2. 仮想環境と依存関係をインストール:
   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1

   pip install -r requirements.txt
   ```
3. `.env.example` を `.env` にコピーし中身を埋める：
   - `LINE_CHANNEL_ACCESS_TOKEN`（Messaging APIタブ > チャネルアクセストークン）
   - `LINE_CHANNEL_SECRET`（Basic settingsタブ > Channel secret）
   - `OPENAI_API_KEY`（OpenAIのAPIキー）
4. アプリを起動:
   ```bash
   python app.py
   ```
5. ngrok をインストールし、ポート3000を公開:
   ```bash
   ngrok http 3000
   ```
   表示された `https://xxxx.ngrok.io` を控える。

6. LINE Developers コンソールで Webhook を設定：
   - Messaging API タブ → Webhook settings
   - Webhook URL に `https://xxxx.ngrok.io/webhook` を入力して「更新」
   - 「Use webhook」を有効化 → 「Verify」をクリックして成功することを確認
   - ついでに「Webhook redelivery」も有効化推奨

7. Bot を友だち追加し、メッセージを送って動作確認。

## デプロイ（Render 例）

1. GitHubにこのプロジェクトをプッシュ
2. Renderで「New +」→「Web Service」→ リポジトリを選択
3. Build Command: `pip install -r requirements.txt`
   Start Command: `gunicorn app:app --preload --bind 0.0.0.0:$PORT`
4. Environment → 環境変数に `.env` の値を登録
5. デプロイ後、RenderのURL（例: `https://your-app.onrender.com/webhook`）をLINEのWebhook URLに設定

## 注意
- このサンプルはテキストメッセージのみ対応。画像/スタンプ等は未対応です。
- 翻訳品質はモデル・プロンプトに依存します。必要に応じて `SYSTEM_PROMPT` を調整してください。
- OpenAIの利用には料金が発生します。無料枠やレート制限に注意してください。

## 参考リンク
- LINE Developers: https://developers.line.biz/
- Messaging API: https://developers.line.biz/en/docs/messaging-api/
- LINE Python SDK: https://github.com/line/line-bot-sdk-python
- OpenAI API: https://platform.openai.com/docs
