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

# Store verification codes and bot configuration
verification_codes = {}
bot_config = {
    "verification_category": None  # Will store the category ID
}

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

# Custom help command
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

# NEW COMMAND: Set Category for verification rooms
@bot.command()
async def setcategory(ctx, *, category_name: str = None):
    """Sets the category for verification rooms. Usage: !setcategory Category Name"""
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need administrator permissions to use this command.")
        return
    
    if not category_name:
        await ctx.send("Please provide a category name. Usage: `!setcategory Category Name`")
        return
    
    # Find the category or create it if it doesn't exist
    category = discord.utils.get(ctx.guild.categories, name=category_name)
    
    if not category:
        try:
            category = await ctx.guild.create_category(name=category_name)
            await ctx.send(f"Category '{category_name}' created successfully!")
        except discord.Forbidden:
            await ctx.send("I don't have permission to create categories.")
            return
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            return
    
    # Store the category ID in the bot configuration
    bot_config["verification_category"] = category.id
    await ctx.send(f"Verification category set to '{category_name}'")

# NEW COMMAND: Setup verification channel
@bot.command()
async def setupverify(ctx):
    """Creates a verification channel for new users."""
    # Check if user has admin permissions
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("You need administrator permissions to use this command.")
        return
    
    try:
        # Create or find the verification channel
        verify_channel = discord.utils.get(ctx.guild.text_channels, name="verification")
        
        if not verify_channel:
            verify_channel = await ctx.guild.create_text_channel(name="verification")
            await ctx.send("Created new verification channel.")
        
        # Send verification message
        embed = discord.Embed(
            title="Server Verification",
            description="Welcome to the server! Please wait while we verify your account.",
            color=discord.Color.green()
        )
        
        await verify_channel.send(embed=embed)
        await ctx.send("Verification channel has been set up!")
        
    except discord.Forbidden:
        await ctx.send("I don't have permission to create channels.")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# NEW COMMAND: Verify a user and create a private room
@bot.command()
async def verify(ctx, member: discord.Member = None):
    """Verifies a user and creates a private room. Usage: !verify @username"""
    # Check if user has permission to verify others
    if not ctx.author.guild_permissions.manage_roles:
        await ctx.send("You need 'Manage Roles' permission to verify users.")
        return
    
    if not member:
        await ctx.send("Please mention a user to verify. Usage: `!verify @username`")
        return
    
    # Check if verification category is set
    if not bot_config["verification_category"]:
        await ctx.send("Verification category not set. Please use `!setcategory` first.")
        return
    
    # Get the category
    category = ctx.guild.get_channel(bot_config["verification_category"])
    if not category:
        await ctx.send("Verification category not found. Please use `!setcategory` again.")
        return
    
    try:
        # Create a private channel for the user
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel_name = f"verify-{member.name.lower()}"
        channel = await ctx.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )
        
        # Send welcome message in the new channel
        embed = discord.Embed(
            title="Verification Room",
            description=f"Welcome {member.mention}! This is your private verification room.",
            color=discord.Color.blue()
        )
        
        await channel.send(embed=embed)
        await ctx.send(f"Created verification room for {member.mention}")
        
    except discord.Forbidden:
        await ctx.send("I don't have permission to create channels.")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Event handler for new members
@bot.event
async def on_member_join(member):
    # Check if verification category is set
    if not bot_config["verification_category"]:
        logger.warning(f"Verification category not set when {member} joined")
        return
    
    # Get the category
    category = member.guild.get_channel(bot_config["verification_category"])
    if not category:
        logger.warning(f"Verification category not found when {member} joined")
        return
    
    try:
        # Create a private channel for the user
        overwrites = {
            member.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            member.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel_name = f"verify-{member.name.lower()}"
        channel = await member.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )
        
        # Send welcome message in the new channel
        embed = discord.Embed(
            title="Verification Room",
            description=f"Welcome {member.mention}! This is your private verification room.",
            color=discord.Color.blue()
        )
        
        await channel.send(embed=embed)
        logger.info(f"Created verification room for new member {member}")
        
    except Exception as e:
        logger.error(f"Error creating verification room for {member}: {e}")

if __name__ == '__main__':
    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Set your token here
    TOKEN = os.environ.get("DISCORD_TOKEN")
    
    # Start the Discord bot
    bot.run(TOKEN)