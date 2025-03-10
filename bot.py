import discord
import random
import string
import asyncio
import os
from flask import Flask, request, jsonify
from threading import Thread
from datetime import datetime
from discord.ext import commands
import logging

# Discord bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'Bot is logged in as {bot.user}')
    print(f'Bot is in {len(bot.guilds)} servers')
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

# Command: Ping
@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f'Pong! Latency: {latency}ms')

# Flask app setup
app = Flask(__name__)

# Store verification codes
verification_codes = {}

def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@app.route('/api/verification/request', methods=['POST'])
def request_verification():
    data = request.json
    username = data.get('discordUsername')

    if not username:
        return jsonify({'success': False, 'message': 'Discord username is required'}), 400

    code = generate_code()
    verification_codes[username] = code

    # Schedule the DM to be sent
    asyncio.run_coroutine_threadsafe(send_verification_dm(username, code), bot.loop)

    return jsonify({'success': True, 'message': 'Verification code sent'})

@app.route('/api/verification/verify', methods=['POST'])
def verify_code():
    data = request.json
    username = data.get('discordUsername')
    code = data.get('code')

    if not username or not code:
        return jsonify({'success': False, 'message': 'Username and code are required'}), 400

    stored_code = verification_codes.get(username)

    if not stored_code:
        return jsonify({'success': False, 'message': 'No verification code found for this user'}), 400

    if code == stored_code:
        verification_codes.pop(username)
        return jsonify({'success': True, 'message': 'Verification successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid verification code'}), 400

async def send_verification_dm(username, code):
    try:
        user = None
        for guild in bot.guilds:
            for member in guild.members:
                if f"{member.name}#{member.discriminator}" == username:
                    user = member
                    break
            if user:
                break

        if not user:
            print(f"Could not find user: {username}")
            return

        await user.send(f"Your verification code is: **{code}**")
        print(f"Verification code sent to {username}")
    except Exception as e:
        print(f"Error sending DM to {username}: {e}")

def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    TOKEN = os.environ.get("DISCORD_TOKEN")
    bot.run(TOKEN)
