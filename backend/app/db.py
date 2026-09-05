import os
import json
import time
import base64
import hmac
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

# Load environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "stock-research-agent-secret-key-12345")

# Dialect selection and Engine configuration
if not DATABASE_URL:
    print("WARNING: DATABASE_URL is not set. Falling back to local SQLite: stock_research.db")
    db_url = "sqlite:///stock_research.db"
else:
    db_url = DATABASE_URL
    # Sanitize postgres protocol for SQLAlchemy compatibility
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

# Connect with appropriate connection pool configurations
if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url, poolclass=QueuePool, pool_size=5, max_overflow=10)

def init_db():
    """Create tables if they do not exist based on database dialect."""
    dialect = engine.dialect.name
    
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                summary TEXT DEFAULT '',
                recent_messages TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS market_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
        else:
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chats (
                id VARCHAR(50) PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(100) NOT NULL,
                summary TEXT DEFAULT '',
                recent_messages JSONB DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))
            conn.execute(text("""
            CREATE TABLE IF NOT EXISTS market_knowledge (
                id SERIAL PRIMARY KEY,
                category VARCHAR(100) NOT NULL,
                topic VARCHAR(200) NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """))

# Import RAG seeding and run database initialization
from app.rag import seed_market_knowledge
init_db()
seed_market_knowledge(engine)


# --- SECURITY & AUTHENTICATION HELPERS ---

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256 (safe, pure python)."""
    salt = os.urandom(16)
    rounds = 100000
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
    salt_b64 = base64.b64encode(salt).decode()
    key_b64 = base64.b64encode(key).decode()
    return f"pbkdf2_sha256${rounds}${salt_b64}${key_b64}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify standard PBKDF2-SHA256 password hash."""
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        rounds = int(parts[1])
        salt = base64.b64decode(parts[2])
        expected_key = base64.b64decode(parts[3])
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, rounds)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False

def create_access_token(data: dict, expires_in: int = 86400) -> str:
    """Generate lightweight pure-Python JWT-style access token."""
    payload = data.copy()
    payload["exp"] = int(time.time()) + expires_in
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    signature = hmac.new(
        JWT_SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{payload_b64}.{sig_b64}"

def verify_access_token(token: str) -> Optional[dict]:
    """Verify access token and return payloads."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig_b64 = parts
        
        # Restore base64 padding
        payload_pad = payload_b64 + "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_pad).decode())
        
        if payload.get("exp", 0) < time.time():
            return None  # Token expired
            
        expected_signature = hmac.new(
            JWT_SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_signature).decode().rstrip("=")
        
        if hmac.compare_digest(sig_b64, expected_sig_b64):
            return payload
    except Exception:
        return None
    return None

# --- DATABASE CRUD OPERATIONS ---

def create_user(username: str, password_raw: str) -> Optional[int]:
    """Register a new user, return user_id or None if username exists."""
    password_hash = hash_password(password_raw)
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO users (username, password_hash) VALUES (:username, :password_hash) RETURNING id"),
                {"username": username, "password_hash": password_hash}
            )
            return result.scalar()
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Fetch user detail by username."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, username, password_hash FROM users WHERE username = :username"),
            {"username": username}
        ).mappings().first()
        return dict(result) if result else None

def create_chat(user_id: int, chat_id: str, title: str) -> Optional[Dict[str, Any]]:
    """Initialize a new chat in the DB."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO chats (id, user_id, title, summary, recent_messages) VALUES (:id, :user_id, :title, '', '[]')"),
                {"id": chat_id, "user_id": user_id, "title": title}
            )
        return {"id": chat_id, "user_id": user_id, "title": title, "summary": "", "recent_messages": []}
    except Exception as e:
        print(f"Error creating chat: {e}")
        return None

def get_user_chats(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all chats for a user, ordered by last updated."""
    with engine.connect() as conn:
        results = conn.execute(
            text("SELECT id, title, summary, recent_messages, updated_at FROM chats WHERE user_id = :user_id ORDER BY updated_at DESC"),
            {"user_id": user_id}
        ).mappings().all()
        
        chats = []
        for r in results:
            chat = dict(r)
            # Normalize recent_messages to list
            if isinstance(chat["recent_messages"], str):
                try:
                    chat["recent_messages"] = json.loads(chat["recent_messages"])
                except Exception:
                    chat["recent_messages"] = []
            chats.append(chat)
        return chats

def get_chat(chat_id: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch specific chat details."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id, title, summary, recent_messages FROM chats WHERE id = :chat_id AND user_id = :user_id"),
            {"chat_id": chat_id, "user_id": user_id}
        ).mappings().first()
        
        if result:
            chat = dict(result)
            if isinstance(chat["recent_messages"], str):
                try:
                    chat["recent_messages"] = json.loads(chat["recent_messages"])
                except Exception:
                    chat["recent_messages"] = []
            return chat
        return None

def update_chat_history(chat_id: str, user_id: int, summary: str, recent_messages: List[Dict[str, Any]], title: Optional[str] = None) -> bool:
    """Save updated running summary and recent messages (keeps it lightweight)."""
    try:
        recent_messages_str = json.dumps(recent_messages)
        
        # Dialect check to adapt json binding type
        dialect = engine.dialect.name
        bind_messages = recent_messages_str if dialect == "sqlite" else recent_messages
        
        with engine.begin() as conn:
            if title:
                conn.execute(
                    text("""
                    UPDATE chats 
                    SET summary = :summary, recent_messages = :recent_messages, title = :title, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :chat_id AND user_id = :user_id
                    """),
                    {"summary": summary, "recent_messages": bind_messages, "title": title, "chat_id": chat_id, "user_id": user_id}
                )
            else:
                conn.execute(
                    text("""
                    UPDATE chats 
                    SET summary = :summary, recent_messages = :recent_messages, updated_at = CURRENT_TIMESTAMP
                    WHERE id = :chat_id AND user_id = :user_id
                    """),
                    {"summary": summary, "recent_messages": bind_messages, "chat_id": chat_id, "user_id": user_id}
                )
        return True
    except Exception as e:
        print(f"Error updating chat: {e}")
        return False

def delete_chat(chat_id: str, user_id: int) -> bool:
    """Delete a chat."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM chats WHERE id = :chat_id AND user_id = :user_id"),
                {"chat_id": chat_id, "user_id": user_id}
            )
        return True
    except Exception as e:
        print(f"Error deleting chat: {e}")
        return False
