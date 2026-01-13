import os
import discord
from discord.ext import commands
from openai import OpenAI
from flask import Flask
from threading import Thread

# --- 設定読み込み ---
# ※後でRenderの画面で環境変数を設定します
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- OpenRouter (OpenAI互換) の設定 ---
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# --- Discord Botの設定 ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Webサーバー (Render用) ---
app = Flask('')

@app.route('/')
def home():
    return "I am alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Botの動作 ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Botへのメンション、または特定のキーワードで反応するようにする
    if bot.user in message.mentions:
        async with message.channel.typing():
            try:
                # ユーザーのメッセージを取得（メンション部分は削除するなど適宜調整）
                user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()

                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://discord.com", 
                        "X-Title": "My Discord Bot",
                    },
                    model="openai/gpt-oss-120b:free", # 無料モデルを指定
                    messages=[
                        {"role": "system", "content": "あなたはtoxic aiです。あなたはDiscordサーバーに常駐する「口が悪いけど憎めないtoxic bot」。基本スタンスはフレンドリーで距離感ゼロ、初対面でもタメ口。人を傷つけるガチ攻撃はしないが、軽口・煽り・自虐・雑なツッコミは大好物。"},
                        {"role": "user", "content": user_input},
                    ],
                )
                response = completion.choices[0].message.content
                await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"エラーが発生しました: {e}")

    await bot.process_commands(message)

# --- 実行 ---
keep_alive()
bot.run(DISCORD_TOKEN)
