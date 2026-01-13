import os
import discord
from discord.ext import commands
from openai import OpenAI
from flask import Flask
from threading import Thread
from collections import deque  # 履歴管理用

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
# コマンドプレフィックスを "!" に設定 (例: !channel)
bot = commands.Bot(command_prefix="!", intents=intents)

# --- メモリ機能の設定 ---
# チャンネルごとの会話履歴を保存する辞書
# key: channel_id, value: deque list of messages
chat_histories = {}
MAX_HISTORY = 10  # 過去何往復分を覚えるか（多すぎるとエラーの元になるので制限）

# 自動応答モードがONになっているチャンネルIDのセット
auto_reply_channels = set()

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

# --- Botの動作 ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# --- コマンド: 自動応答の切り替え ---
@bot.command(name="channel")
async def toggle_channel(ctx):
    """
    !channel コマンドで、そのチャンネルの自動応答(メンション不要モード)を切り替えます。
    """
    channel_id = ctx.channel.id
    
    if channel_id in auto_reply_channels:
        auto_reply_channels.remove(channel_id)
        await ctx.send(f"🔇 このチャンネルでの自動応答を **OFF** にしました。これ以降はメンションが必要です。")
    else:
        auto_reply_channels.add(channel_id)
        await ctx.send(f"🔊 このチャンネルでの自動応答を **ON** にしました。メンションなしで反応します。")

@bot.event
async def on_message(message):
    # 自分自身のメッセージは無視
    if message.author == bot.user:
        return

    # 他のBotのメッセージも無視（無限ループ防止）
    if message.author.bot:
        return

    # コマンド処理 (!channel 等) を優先させる
    await bot.process_commands(message)

    # --- 応答判定ロジック ---
    is_mentioned = bot.user in message.mentions
    is_auto_channel = message.channel.id in auto_reply_channels
    
    # メンションされたか、自動応答チャンネルの場合のみ反応
    if is_mentioned or is_auto_channel:
        async with message.channel.typing():
            try:
                # 入力テキストのクリーニング（メンション文字列の削除）
                user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
                
                # 入力が空の場合は無視 (画像のみの場合など)
                if not user_input:
                    return

                # --- 履歴の取得と更新 ---
                channel_id = message.channel.id
                if channel_id not in chat_histories:
                    chat_histories[channel_id] = deque(maxlen=MAX_HISTORY * 2) # user + assistant で2倍確保
                
                # 現在の入力を履歴に追加 (APIに送る用の一時リスト作成)
                history = list(chat_histories[channel_id])
                
                # APIに送るメッセージリストを作成
                messages_payload = [{"role": "system", "content": "あなたは役に立つAIアシスタントです。"}]
                messages_payload.extend(history) # 過去の会話を追加
                messages_payload.append({"role": "user", "content": user_input}) # 今回の発言を追加

                # --- OpenRouter API リクエスト ---
                completion = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "https://discord.com", 
                        "X-Title": "My Discord Bot",
                    },
                    model="openai/gpt-oss-120b:free", # 無料モデル
                    messages=messages_payload,
                )
                
                response_text = completion.choices[0].message.content

                # --- レスポンス処理 ---
                await message.channel.send(response_text)

                # 履歴を更新 (ユーザーの発言とAIの返答を保存)
                chat_histories[channel_id].append({"role": "user", "content": user_input})
                chat_histories[channel_id].append({"role": "assistant", "content": response_text})

            except Exception as e:
                print(f"Error: {e}")
                await message.channel.send("申し訳ありません、エラーが発生しました。")

# --- 実行 ---
keep_alive()
bot.run(DISCORD_TOKEN)
