# Database operations module for InternHunt
import pymysql
import sqlite3
import streamlit as st
import logging
import os
from typing import Optional, Dict, Any
from config import Config, default_db_type

logger = logging.getLogger(__name__)

def save_env_config(db_type: str, host: str = '', port: int = 3306, 
                    user: str = '', password: str = '', database: str = ''):
    """Save database configuration to the .env file"""
    # Locate .env in workspace root
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    # Read existing lines
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
    # Map key to its line index
    keys_map = {}
    for i, line in enumerate(lines):
        clean = line.strip()
        if clean and not clean.startswith('#') and '=' in clean:
            parts = clean.split('=', 1)
            keys_map[parts[0].strip()] = i
            
    updates = {
        'DB_TYPE': db_type,
        'DB_HOST': host,
        'DB_PORT': str(port),
        'DB_USER': user,
        'DB_PASSWORD': password,
        'DB_NAME': database
    }
    
    for k, v in updates.items():
        if k in keys_map:
            lines[keys_map[k]] = f"{k}={v}\n"
        else:
            lines.append(f"{k}={v}\n")
            
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
    for k, v in updates.items():
        os.environ[k] = v

class DatabaseManager:
    """Handles all database operations supporting both MySQL and SQLite"""
    
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_type = default_db_type()
        self._connect()
    
    def _connect(self):
        """Establish database connection"""
        self.db_type = default_db_type()
        try:
            if self.db_type == 'sqlite':
                db_name = os.getenv('DB_NAME', 'cv')
                self.connection = sqlite3.connect(f"{db_name}.db", check_same_thread=False)
                self.cursor = self.connection.cursor()
                self._initialize_database()
                logger.info("SQLite Database connected successfully")
            else:
                # Only attempt connection if database credentials are configured
                if Config.DB_CONFIG.get('password') or Config.DB_CONFIG.get('user') != 'root':
                    self.connection = pymysql.connect(**{k: v for k, v in Config.DB_CONFIG.items() if k != 'db_type'})
                    self.cursor = self.connection.cursor()
                    self._initialize_database()
                    logger.info("MySQL Database connected successfully")
                else:
                    logger.info("Database credentials not configured - running without database features")
                    self.connection = None
                    self.cursor = None
        except Exception as e:
            logger.warning(f"Database connection failed: {e} - continuing without database features")
            self.connection = None
            self.cursor = None
    
    def _initialize_database(self):
        """Create database and tables if they don't exist"""
        try:
            if self.db_type == 'sqlite':
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS user_data (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL,
                    Email_ID TEXT NOT NULL,
                    resume_score TEXT NOT NULL,
                    Timestamp TEXT NOT NULL,
                    Page_no TEXT NOT NULL,
                    Predicted_Field TEXT NOT NULL,
                    User_level TEXT NOT NULL,
                    Actual_skills TEXT NOT NULL,
                    Recommended_skills TEXT NOT NULL,
                    Recommended_courses TEXT NOT NULL
                );
                """
                self.cursor.execute(create_table_sql)
                self.connection.commit()
            else:
                db_name = Config.DB_CONFIG.get('database') or 'cv'
                self.cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name};")
                self.cursor.execute(f"USE {db_name};")
                
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS user_data (
                    ID INT NOT NULL AUTO_INCREMENT,
                    Name VARCHAR(500) NOT NULL,
                    Email_ID VARCHAR(500) NOT NULL,
                    resume_score VARCHAR(8) NOT NULL,
                    Timestamp VARCHAR(50) NOT NULL,
                    Page_no VARCHAR(5) NOT NULL,
                    Predicted_Field TEXT NOT NULL,
                    User_level TEXT NOT NULL,
                    Actual_skills TEXT NOT NULL,
                    Recommended_skills TEXT NOT NULL,
                    Recommended_courses TEXT NOT NULL,
                    PRIMARY KEY (ID)
                );
                """
                self.cursor.execute(create_table_sql)
                self.connection.commit()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            
    def connect_with_credentials(self, db_type: str, host: str = 'localhost', port: int = 3306, 
                                 user: str = 'root', password: str = '', database: str = 'cv') -> tuple:
        """Attempt connection with specific credentials and update configurations if successful"""
        try:
            self.close()
            self.db_type = db_type.lower()
            
            if self.db_type == 'sqlite':
                self.connection = sqlite3.connect(f"{database}.db", check_same_thread=False)
                self.cursor = self.connection.cursor()
                self._initialize_database()
                
                # Update Config
                Config.DB_CONFIG['db_type'] = 'sqlite'
                Config.DB_CONFIG['database'] = database
                
                # Save to environment and .env
                save_env_config('sqlite', database=database)
                return True, "Connected to SQLite successfully!"
            else:
                config = {
                    'host': host,
                    'port': int(port),
                    'user': user,
                    'password': password,
                    'database': database,
                    'charset': 'utf8mb4'
                }
                self.connection = pymysql.connect(**config)
                self.cursor = self.connection.cursor()
                self._initialize_database()
                
                # Update Config
                Config.DB_CONFIG.update(config)
                Config.DB_CONFIG['db_type'] = 'mysql'
                
                # Save to environment and .env
                save_env_config('mysql', host, port, user, password, database)
                return True, "Connected to MySQL successfully!"
        except Exception as e:
            self.connection = None
            self.cursor = None
            # Revert to standard initialization
            self._connect()
            return False, str(e)
    
    def insert_user_data(self, name: str, email: str, res_score: int, 
                        timestamp: str, no_of_pages: int, reco_field: str,
                        cand_level: str, skills: list, recommended_skills: list,
                        courses: list) -> bool:
        """Insert user data into database"""
        if not self.connection:
            logger.info("Database not available - skipping data insertion")
            return False
            
        try:
            placeholder = '?' if self.db_type == 'sqlite' else '%s'
            insert_sql = f"""
            INSERT INTO user_data (Name, Email_ID, resume_score, Timestamp, Page_no, 
                                  Predicted_Field, User_level, Actual_skills, 
                                  Recommended_skills, Recommended_courses)
            VALUES ({', '.join([placeholder] * 10)})
            """
            
            values = (
                name,
                email,
                str(res_score),
                timestamp,
                str(no_of_pages),
                reco_field,
                cand_level,
                ', '.join(skills),
                ', '.join(recommended_skills),
                ', '.join(courses)
            )
            
            self.cursor.execute(insert_sql, values)
            self.connection.commit()
            logger.info("User data inserted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to insert user data: {e}")
            return False
    
    def get_user_data(self, limit: int = 100) -> Optional[list]:
        """Retrieve user data from database"""
        if not self.connection:
            return None
        
        try:
            self.cursor.execute(f"SELECT * FROM user_data ORDER BY ID DESC LIMIT {limit}")
            return self.cursor.fetchall()
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return None
    
    def close(self):
        """Close database connection"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
        except Exception:
            pass
        finally:
            self.cursor = None
            self.connection = None
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.close()

# Global database instance
db_manager = DatabaseManager()
