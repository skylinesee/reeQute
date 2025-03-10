from flask import Flask, request, jsonify
import asyncio
import os
from utils import generate_code, verification_codes, logger

# Create Flask app
app = Flask(__name__)

# Import bot and send_verification_dm function
# We import here to avoid circular imports
from bot import bot, send_verification_dm

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
    asyncio.run_coroutine_threadsafe(send_verification_dm(username, code), bot.loop)
    
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

# Health check endpoint for Railway
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'bot_connected': bot.is_ready()})

# Run the Flask app if this file is executed directly
if __name__ == '__main__':
    # Use PORT environment variable for Railway compatibility
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)