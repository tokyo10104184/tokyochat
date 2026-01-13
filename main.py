import os
import discord
from discord.ext import commands
from openai import OpenAI
from flask import Flask
from threading import Thread
from collections import deque

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
    app.run(host='0.0.0.0', port=8000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 状態管理用変数 ---
# チャンネルごとの会話履歴 {channel_id: [messages...]}
conversation_history = {}
# 会話履歴の最大保持数（増やしすぎるとエラーになる可能性があります）
MAX_HISTORY = 10 

# 自動応答モードがオンになっているチャンネルIDのリスト
active_channels = set()

# --- Botの動作 ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# --- !channel コマンド ---
@bot.command()
async def channel(ctx):
    """現在のチャンネルでの自動応答モードを切り替えます"""
    channel_id = ctx.channel.id
    if channel_id in active_channels:
        active_channels.remove(channel_id)
        # モードをオフにした際、履歴もリセットしたい場合は以下をコメントアウト解除
        # if channel_id in conversation_history:
        #     del conversation_history[channel_id]
        await ctx.send("🔇 このチャンネルでの自動応答を**オフ**にしました。（メンション時のみ反応します）")
    else:
        active_channels.add(channel_id)
        await ctx.send("🔊 このチャンネルでの自動応答を**オン**にしました。（全てのメッセージに反応します）")

@bot.event
async def on_message(message):
    # Bot自身のメッセージは無視
    if message.author == bot.user:
        return

    # コマンド処理 (!channel など) を優先
    await bot.process_commands(message)

    # 反応する条件: 
    # 1. Botへのメンションがある
    # OR
    # 2. 自動応答モードのチャンネルである (かつコマンド開始文字ではない)
    is_mentioned = bot.user in message.mentions
    is_active_channel = message.channel.id in active_channels
    is_command = message.content.startswith(bot.command_prefix)

    if (is_mentioned or (is_active_channel and not is_command)):
        async with message.channel.typing():
            try:
                # ユーザー入力を整形 (メンション部分を削除)
                user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
                if not user_input:
                    return # 空メッセージなら無視

                channel_id = message.channel.id

                # 履歴がなければ初期化
                if channel_id not in conversation_history:
                    conversation_history[channel_id] = [
                        {"role": "system", "content": "あなたは役に立つAIアシスタントです。"}
                    ]

                # ユーザーのメッセージを履歴に追加
                conversation_history[channel_id].append({"role": "user", "content": user_input})

                # 履歴制限 (システムプロンプト + 最新のN件のみを残す)
                # systemプロンプト(index 0)は維持し、それ以外をスライスして結合
                if len(conversation_history[channel_id]) > MAX_HISTORY:
                    system_msg = conversation_history[channel_id][0]
                    recent_msgs = conversation_history[channel_id][-(MAX_HISTORY-1):]
                    conversation_history[channel_id] = [system_msg] + recent_msgs

                # APIリクエスト (履歴全体を送信)
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://discord.com", 
                        "X-Title": "My Discord Bot",
                    },
                    model="openai/gpt-oss-120b:free",
                    messages=conversation_history[channel_id], # ここで履歴を渡す
                )
                
                response = completion.choices[0].message.content
                
                # AIの応答を履歴に追加
                conversation_history[channel_id].append({"role": "assistant", "content": response})

                await message.channel.send(response)

            except Exception as e:
                # エラー時は履歴に追加しないほうが安全かもしれません
                await message.channel.send(f"エラーが発生しました: {e}")
                print(f"Error: {e}")

# --- 実行 ---
keep_alive()
bot.run(DISCORD_TOKEN)
