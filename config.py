import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Base configuration."""
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    FLASK_APP = 'app.py'
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Session settings
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    
    # Logging settings
    LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'logs'))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # Microsoft Graph API settings
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
    MICROSOFT_TENANT_ID = os.environ.get('MICROSOFT_TENANT_ID', 'common')
    MICROSOFT_AUTHORITY = os.environ.get('MICROSOFT_AUTHORITY', 'https://login.microsoftonline.com/common')
    MICROSOFT_REDIRECT_URI = os.environ.get('MICROSOFT_REDIRECT_URI', 'http://localhost:5000/auth/callback')
    MICROSOFT_SCOPE = os.environ.get('MICROSOFT_SCOPE', 'User.Read Calendars.ReadWrite OnlineMeetings.ReadWrite')
    
    def __init__(self):
        # Validate critical settings
        if not self.MICROSOFT_CLIENT_ID:
            print("WARNING: MICROSOFT_CLIENT_ID environment variable is not set!")
        if not self.MICROSOFT_CLIENT_SECRET:
            print("WARNING: MICROSOFT_CLIENT_SECRET environment variable is not set!")

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False

class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    # In production, use a properly generated secret key
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Use HTTPS for redirect URI in production
    MICROSOFT_REDIRECT_URI = os.environ.get('MICROSOFT_REDIRECT_URI', 'https://your-app-domain.com/auth/callback')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Select config based on environment variable or default to development
def get_config():
    env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])()