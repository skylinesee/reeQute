import random
import string
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Store verification codes
verification_codes = {}

# Generate a random verification code
def generate_code(length=6):
    return ''.join(random.choices(string.digits, k=length))