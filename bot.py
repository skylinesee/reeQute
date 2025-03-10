import discord
import random
import string
import asyncio
import os
from flask import Flask, request, jsonify
from threading import Thread
import logging
from discord.ext import commands

# Flask app setup
app = Flask(__name__)

# Store verification codes
verification_codes = {}

# Generate a random verification code
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Discord bot setup with PROPER INTENTS
intents = discord.Intents.default()
intents.message_content = True  # Privileged intent
intents.members = True          # Privileged intent - needed to access guild members
bot = commands.Bot(command_prefix='!', intents=intents)





# Flask API endpoints
@app.route('/api/verification/request', methods=['POST'])
def request_verification():
    data = request.json
    username = data.get('discordUsername')
    
    if not username:
        return jsonify({'success': False, 'message': 'Discord username is required'}), 400
    
    # Generate a verification code
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
        # Remove the code after successful verification
        verification_codes.pop(username)
        return jsonify({'success': True, 'message': 'Verification successful'})
    else:
        return jsonify({'success': False, 'message': 'Invalid verification code'}), 400

async def send_verification_dm(username, code):
    try:
        user = None
        logger.info(f"Attempting to find user: {username}")
        
        # Check if username includes discriminator (e.g., username#1234)
        if '#' in username:
            name, discriminator = username.split('#')
            logger.info(f"Looking for user with name: {name} and discriminator: {discriminator}")
            for guild in bot.guilds:
                for member in guild.members:
                    if member.name.lower() == name.lower() and member.discriminator == discriminator:
                        user = member
                        logger.info(f"Found user in guild: {guild.name}")
                        break
                if user:
                    break
        else:
            # Try to find by username only (less reliable)
            logger.info(f"Looking for user with name: {username} (no discriminator)")
            for guild in bot.guilds:
                for member in guild.members:
                    if member.name.lower() == username.lower():
                        user = member
                        logger.info(f"Found user in guild: {guild.name}")
                        break
                if user:
                    break
        
        if not user:
            logger.error(f"Could not find user: {username}")
            return
        
        # Send the DM
        logger.info(f"Sending verification code to user: {user.name}")
        await user.send(f"Your verification code is: **{code}**\nPlease enter this code in the application to complete verification.")
        logger.info(f"Verification code sent to {username}")
    except Exception as e:
        logger.error(f"Error sending DM to {username}: {e}")

# Run Flask in a separate thread
def run_flask():
    app.run(host='0.0.0.0', port=5000)

# Botun varsayılan yardım komutunu değiştirme
class MyHelpCommand(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        # Show main commands
        embed = discord.Embed(title="Bot Commands", description="Check out the bot commands!", color=discord.Color.blue())
        for cog, commands in mapping.items():
            command_list = [command.name for command in commands if not command.hidden]
            if command_list:
                embed.add_field(name=cog.qualified_name if cog else "Main Commands", value="\n".join(command_list), inline=False)
        channel = self.context.channel
        await channel.send(embed=embed)

    async def send_command_help(self, command):
        # Information about a single command
        embed = discord.Embed(title=f"{command.name} Command", description=command.help or "No description.", color=discord.Color.green())
        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        # Information about a specific cog
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", description="Commands under this cog", color=discord.Color.orange())
        for command in cog.get_commands():
            embed.add_field(name=command.name, value=command.help or "No description.", inline=False)
        await self.context.send(embed=embed)

# Set the custom help command
bot.help_command = MyHelpCommand()

# Bot's on_ready event (when bot is ready)
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    # Set the bot's presence (status)
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

# Ping command
@bot.command()
async def ping(ctx):
    """Ping command!"""
    await ctx.send('Pong!')

# Roll command
@bot.command()
async def roll(ctx, dice: str):
    """Roll a dice! Example usage: !roll 2d6"""
    await ctx.send(f'Rolled dice result: {dice}')

# Profile command
@bot.command()
async def profile(ctx, member: discord.Member = None):
    """Shows a user's profile picture."""
    member = member or ctx.author  # Use the provided member or the command author
    await ctx.send(member.avatar.url)


if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Set your token here
    TOKEN = os.environ.get("DISCORD_TOKEN")
    
    # Start the Discord bot
    bot.run(TOKEN)
