import os
import discord
from discord.ext import commands
from openai import OpenAI
from flask import Flask
from threading import Thread

# --- 設定読み込み ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# トークンがない場合に警告を出して終了させる（デバッグ用）
if not DISCORD_TOKEN:
    print("エラー: DISCORD_TOKEN 環境変数が設定されていません。")
if not OPENROUTER_API_KEY:
    print("警告: OPENROUTER_API_KEY 環境変数が設定されていません。")

# --- OpenRouter 設定 ---
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# --- Discord Bot 設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Webサーバー (Koyebのヘルスチェック用) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Alive!"

def run():
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Botの動作 ---
@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user}')
    print(f'現在のIntents設定: message_content={intents.message_content}')

@bot.event
async def on_message(message):
    # 自分自身のメッセージは無視
    if message.author == bot.user:
        return

    # デバッグ: メッセージを受信したことをログに出す
    # (これがコンソールに出ない場合、Developer PortalのIntent設定が原因です)
    print(f"メッセージ受信: {message.author}: {message.content}")

    # Botへのメンションで反応
    if bot.user in message.mentions:
        print("Botへのメンションを検知しました。AI生成を開始します...")
        async with message.channel.typing():
            try:
                user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
                
                # 入力が空の場合の対策
                if not user_input:
                    await message.channel.send("何か話しかけてください！")
                    return

                # モデルを比較的安定している無料モデルに変更 (必要に応じて変更してください)
                # 例: google/gemini-2.0-flash-exp:free, meta-llama/llama-3-8b-instruct:free など
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://discord.com", 
                        "X-Title": "Discord Bot",
                    },
                    model="openai/gpt-oss-120b:free", 
                    messages=[
                        {"role": "system", "content": "あなたは役に立つAIアシスタントです。"},
                        {"role": "user", "content": user_input},
                    ],
                )
                
                response = completion.choices[0].message.content
                
                # エラーではないが中身が空の場合
                if not response:
                    response = "AIからの応答がありませんでした。"

                await message.channel.send(response)
                print("返信完了")

            except Exception as e:
                error_msg = f"エラーが発生しました: {e}"
                print(error_msg)
                await message.channel.send(error_msg)

    # コマンド処理（もし今後追加する場合に必要）
    await bot.process_commands(message)

# --- 実行 ---
keep_alive()

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Botを起動できませんでした。DISCORD_TOKENを確認してください。")
