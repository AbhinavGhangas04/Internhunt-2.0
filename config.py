# Configuration file for InternHunt application
import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def default_db_type() -> str:
    """Prefer SQLite when MySQL credentials are not configured (e.g. Streamlit Cloud)."""
    explicit = os.getenv('DB_TYPE')
    if explicit:
        return explicit.lower()
    if os.getenv('DB_PASSWORD') or os.getenv('DB_HOST'):
        return 'mysql'
    return 'sqlite'


class Config:
    """Application configuration class"""
    
    # Database Configuration
    DB_CONFIG = {
        'host': os.getenv('DB_HOST'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'charset': 'utf8mb4',
        'ssl': {
            'ca': os.getenv('CA_CERT_PATH'),
        } if os.getenv('CA_CERT_PATH') else None,   # Only include SSL if CA path is set
    }

    # API Keys
    JOOBLE_API_KEY = os.getenv('JOOBLE_API_KEY', '4d4c75a1-1761-49c7-a003-71ed93beaf52')
    ADZUNA_APP_ID = os.getenv('ADZUNA_APP_ID', '1178ed1c')
    ADZUNA_API_KEY = os.getenv('ADZUNA_API_KEY', '2e96a2f4573fff0502a2a081c21b6810')
    ADZUNA_COUNTRY = os.getenv('ADZUNA_COUNTRY', 'in')

    # Application Settings
    APP_TITLE = "InternHunt - Your Internship Finder"
    APP_ICON = '🎯'
    UPLOAD_DIR = './Uploaded_Resumes/'

    # Skill matching settings
    FUZZY_THRESHOLD = 50
    DIRECT_MATCH_WEIGHT = 1.0
    SIMILARITY_MATCH_WEIGHT = 0.5
    FIELD_SCORE_THRESHOLD = 0.5

    @classmethod
    def get_db_connection_string(cls) -> str:
        """Get database connection string"""
        return f"mysql://{cls.DB_CONFIG['user']}:{cls.DB_CONFIG['password']}@{cls.DB_CONFIG['host']}:{cls.DB_CONFIG['port']}/{cls.DB_CONFIG['database']}"

    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return status"""
        issues = []
        db_type = default_db_type()

        if db_type == 'mysql' and not cls.DB_CONFIG['password']:
            issues.append("Database password not set (required for MySQL)")

        if not os.path.exists(cls.UPLOAD_DIR):
            try:
                os.makedirs(cls.UPLOAD_DIR, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create upload directory: {e}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }
