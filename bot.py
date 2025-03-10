import discord
import random
import string
import asyncio
import os
from flask import Flask, request, jsonify
from threading import Thread
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Discord bot setup with PROPER INTENTS
intents = discord.Intents.default()
intents.message_content = True  # Privileged intent
intents.members = True          # Privileged intent - needed to access guild members
client = discord.Client(intents=intents)

# Flask app setup
app = Flask(__name__)

# Store verification codes
verification_codes = {}

# Generate a random verification code
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))

@client.event
async def on_ready():
    logger.info(f'Bot logged in as {client.user}')
    logger.info(f'Bot is in {len(client.guilds)} guilds')
    
    # Log the names of the guilds the bot is in
    for guild in client.guilds:
        logger.info(f'- {guild.name} (id: {guild.id})')
        logger.info(f'  Member count: {guild.member_count}')

# API endpoint to request a verification code
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
    asyncio.run_coroutine_threadsafe(send_verification_dm(username, code), client.loop)
    
    return jsonify({'success': True, 'message': 'Verification code sent'})

# API endpoint to verify a code
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

# Function to send a DM to a user
async def send_verification_dm(username, code):
    try:
        # Try to find the user by username
        user = None
        logger.info(f"Attempting to find user: {username}")
        
        # Check if username includes discriminator (e.g., username#1234)
        if '#' in username:
            name, discriminator = username.split('#')
            logger.info(f"Looking for user with name: {name} and discriminator: {discriminator}")
            for guild in client.guilds:
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
            for guild in client.guilds:
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

# Health check endpoint for Railway
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'bot_connected': client.is_ready()})

# Run the Flask app in a separate thread
def run_flask():
    # Use PORT environment variable for Railway compatibility
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Get token from environment variable
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        logger.error("Error: No Discord token found. Set the DISCORD_TOKEN environment variable.")
    else:
        # Start the Discord bot
        client.run(TOKEN)