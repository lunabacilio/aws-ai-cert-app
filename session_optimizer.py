"""
Optimization for handling large sessions
This module implements efficient storage to avoid cookie problems
"""
import json
import hashlib
from datetime import datetime

# In-memory cache for large sessions
session_cache = {}

def generate_session_id():
    """Generates a unique ID for the session"""
    timestamp = datetime.now().isoformat()
    return hashlib.md5(timestamp.encode()).hexdigest()[:16]

def store_large_session(questions, quiz_mode):
    """
    Stores large sessions in cache instead of cookies
    Returns a compact session_id
    """
    session_id = generate_session_id()
    
    # Compact data that goes in the cookie
    compact_data = {
        'session_id': session_id,
        'quiz_mode': quiz_mode,
        'total_questions': len(questions),
        'current_question': 0,
        'user_answers': {},
        'correct_answers': 0,
        'start_time': datetime.now().isoformat(),
        'is_large_session': True  # Flag to identify large sessions
    }
    
    # Large data that goes in memory cache
    large_data = {
        'questions': questions,
        'created_at': datetime.now().isoformat()
    }
    
    # Save in cache
    session_cache[session_id] = large_data
    
    return compact_data

def get_session_questions(session_data):
    """
    Retrieves questions from session (from cache or cookie)
    """
    if session_data.get('is_large_session'):
        # Large session - search in cache
        session_id = session_data.get('session_id')
        if session_id in session_cache:
            return session_cache[session_id]['questions']
        else:
            # Cache expired or lost
            return None
    else:
        # Small session - data in cookie
        return session_data.get('questions', [])

def cleanup_expired_sessions():
    """
    Cleans expired sessions from cache (optional)
    """
    # For simplicity, we don't implement automatic cleanup
    # In production, you would use Redis or a database
    pass

def estimate_session_size(questions):
    """
    Estimates the session size in bytes
    """
    # JSON size approximation
    sample_data = {
        'questions': questions[:1] if questions else [],
        'quiz_mode': 'immediate',
        'current_question': 0,
        'user_answers': {},
        'correct_answers': 0
    }
    
    estimated_size = len(json.dumps(sample_data, ensure_ascii=False))
    total_size = estimated_size * len(questions) if questions else 0
    
    return total_size

def should_use_large_session(questions):
    """
    Determines if the large session system should be used
    """
    estimated_size = estimate_session_size(questions)
    # Conservative limit of 3KB (Flask uses 4KB as limit)
    return estimated_size > 3000 or len(questions) > 40
