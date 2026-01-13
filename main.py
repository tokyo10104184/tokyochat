import os
import discord
from discord.ext import commands
from openai import OpenAI
from flask import Flask
from threading import Thread

# --- 設定読み込み ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
    return "Koyeb Bot is Alive!"

def run():
    # Koyebはポート8000を好みます
    app.run(host='0.0.0.0', port=8000)

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

    # Botへのメンションで反応
    if bot.user in message.mentions:
        async with message.channel.typing():
            try:
                user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
                
                # 無料モデルを指定
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://discord.com", 
                        "X-Title": "My Discord Bot",
                    },
                    model="openai/gpt-oss-120b:free",
                    messages=[
                        {"role": "system", "content": "あなたは役に立つAIアシスタントです。"},
                        {"role": "user", "content": user_input},
                    ],
                )
                response = completion.choices[0].message.content
                await message.channel.send(response)
            except Exception as e:
                await message.channel.send(f"エラー: {e}")

    await bot.process_commands(message)

# --- 実行 ---
keep_alive()
bot.run(DISCORD_TOKEN)
