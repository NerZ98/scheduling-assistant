import sqlite3
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import os

class MeetingDatabase:
    """Database handler for storing Microsoft Graph meeting information"""
    
    def __init__(self, db_path='meetings.db', logger=None):
        """
        Initialize the meeting database
        
        Args:
            db_path (str): Path to the SQLite database file
            logger (logging.Logger, optional): Logger instance
        """
        self.db_path = db_path
        
        # Setup logging
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('MeetingDatabase')
            self.logger.setLevel(logging.INFO)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(name)s - %(levelname)s: %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            self.logger.info(f"Initializing meeting database at {self.db_path}")
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            # Create connection and tables
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create sessions table for storing Microsoft user sessions
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                display_name TEXT,
                email TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Create meetings table for storing Microsoft Graph meeting information
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                chat_session_id TEXT,
                ms_meeting_id TEXT,
                subject TEXT,
                body TEXT,
                start_time TEXT,
                end_time TEXT,
                location TEXT,
                online_meeting_url TEXT,
                attendees TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES ms_sessions(session_id)
            )
            ''')
            
            conn.commit()
            conn.close()
            self.logger.info("Meeting database initialized successfully")
        
        except Exception as e:
            self.logger.error(f"Error initializing meeting database: {e}", exc_info=True)
            raise
    
    def save_session(self, session_id: str, user_info: Dict[str, Any], token_info: Dict[str, Any]) -> bool:
        """
        Save Microsoft session information
        
        Args:
            session_id: Flask session ID
            user_info: User information from Microsoft Graph
            token_info: Token information including access and refresh tokens
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if session already exists
            cursor.execute("SELECT session_id FROM ms_sessions WHERE session_id = ?", (session_id,))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing session
                cursor.execute('''
                UPDATE ms_sessions SET
                    user_id = ?,
                    display_name = ?,
                    email = ?,
                    access_token = ?,
                    refresh_token = ?,
                    expires_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
                ''', (
                    user_info.get('id', ''),
                    user_info.get('displayName', ''),
                    user_info.get('mail', user_info.get('userPrincipalName', '')),
                    token_info.get('access_token', ''),
                    token_info.get('refresh_token', ''),
                    token_info.get('expires_at', 0),
                    session_id
                ))
            else:
                # Insert new session
                cursor.execute('''
                INSERT INTO ms_sessions (
                    session_id, user_id, display_name, email,
                    access_token, refresh_token, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    user_info.get('id', ''),
                    user_info.get('displayName', ''),
                    user_info.get('mail', user_info.get('userPrincipalName', '')),
                    token_info.get('access_token', ''),
                    token_info.get('refresh_token', ''),
                    token_info.get('expires_at', 0)
                ))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Microsoft session saved for session {session_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving Microsoft session: {e}", exc_info=True)
            return False
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Get Microsoft session information
        
        Args:
            session_id: Flask session ID
            
        Returns:
            Dict: Session information or empty dict if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM ms_sessions WHERE session_id = ?
            ''', (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                self.logger.debug(f"Found Microsoft session for {session_id}")
                return dict(result)
            else:
                self.logger.debug(f"No Microsoft session found for {session_id}")
                return {}
        
        except Exception as e:
            self.logger.error(f"Error getting Microsoft session: {e}", exc_info=True)
            return {}
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete Microsoft session information
        
        Args:
            session_id: Flask session ID
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM ms_sessions WHERE session_id = ?", (session_id,))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Microsoft session deleted for {session_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting Microsoft session: {e}", exc_info=True)
            return False
    
    def save_meeting(self, session_id: str, chat_session_id: str, meeting_data: Dict[str, Any]) -> int:
        """
        Save Microsoft Graph meeting information
        
        Args:
            session_id: Flask session ID
            chat_session_id: Chat session ID
            meeting_data: Meeting information from Microsoft Graph
            
        Returns:
            int: Meeting ID or 0 if failed
        """
        try:
            # Validate meeting_data
            if not meeting_data or not isinstance(meeting_data, dict) or 'id' not in meeting_data:
                self.logger.error(f"Invalid meeting data: {meeting_data}")
                return 0
                
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert attendees list to JSON string
            attendees = meeting_data.get('attendees', [])
            attendees_json = json.dumps(attendees) if isinstance(attendees, list) else '[]'
            
            # Safely get nested attributes with fallbacks
            ms_meeting_id = meeting_data.get('id', '')
            subject = meeting_data.get('subject', 'Meeting')
            
            # Safely get body content
            body_content = ''
            body = meeting_data.get('body', {})
            if isinstance(body, dict):
                body_content = body.get('content', '')
                
            # Safely get datetime values
            start_time = ''
            end_time = ''
            start_obj = meeting_data.get('start', {})
            end_obj = meeting_data.get('end', {})
            
            if isinstance(start_obj, dict):
                start_time = start_obj.get('dateTime', '')
            if isinstance(end_obj, dict):
                end_time = end_obj.get('dateTime', '')
                
            # Safely get location
            location = ''
            loc_obj = meeting_data.get('location', {})
            if isinstance(loc_obj, dict):
                location = loc_obj.get('displayName', '')
                
            # Safely get online meeting URL
            online_meeting_url = ''
            online_meeting = meeting_data.get('onlineMeeting', {})
            if isinstance(online_meeting, dict):
                online_meeting_url = online_meeting.get('joinUrl', '')
            
            # Check if meeting already exists for this chat session
            cursor.execute('''
            SELECT id, ms_meeting_id FROM ms_meetings 
            WHERE chat_session_id = ?
            ''', (chat_session_id,))
            
            existing = cursor.fetchone()
            
            if existing:
                meeting_id, existing_ms_meeting_id = existing
                
                # Update existing meeting
                cursor.execute('''
                UPDATE ms_meetings SET
                    session_id = ?,
                    ms_meeting_id = ?,
                    subject = ?,
                    body = ?,
                    start_time = ?,
                    end_time = ?,
                    location = ?,
                    online_meeting_url = ?,
                    attendees = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''', (
                    session_id,
                    ms_meeting_id,
                    subject,
                    body_content,
                    start_time,
                    end_time,
                    location,
                    online_meeting_url,
                    attendees_json,
                    meeting_id
                ))
                
                self.logger.info(f"Updated existing meeting for chat session {chat_session_id}")
                conn.commit()
                conn.close()
                return meeting_id
            else:
                # Insert new meeting
                cursor.execute('''
                INSERT INTO ms_meetings (
                    session_id, chat_session_id, ms_meeting_id,
                    subject, body, start_time, end_time,
                    location, online_meeting_url, attendees
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    chat_session_id,
                    ms_meeting_id,
                    subject,
                    body_content,
                    start_time,
                    end_time,
                    location,
                    online_meeting_url,
                    attendees_json
                ))
                
                # Get the ID of the inserted meeting
                meeting_id = cursor.lastrowid
                
                self.logger.info(f"Saved new meeting {meeting_id} for chat session {chat_session_id}")
                conn.commit()
                conn.close()
                return meeting_id
        
        except Exception as e:
            self.logger.error(f"Error saving meeting: {e}", exc_info=True)
            return 0
        
    def get_meeting(self, chat_session_id: str) -> Dict[str, Any]:
        """
        Get meeting information for a chat session
        
        Args:
            chat_session_id: Chat session ID
            
        Returns:
            Dict: Meeting information or empty dict if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM ms_meetings WHERE chat_session_id = ?
            ''', (chat_session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                meeting_data = dict(result)
                
                # Parse attendees JSON
                try:
                    meeting_data['attendees'] = json.loads(meeting_data.get('attendees', '[]'))
                except:
                    meeting_data['attendees'] = []
                
                self.logger.debug(f"Found meeting for chat session {chat_session_id}")
                return meeting_data
            else:
                self.logger.debug(f"No meeting found for chat session {chat_session_id}")
                return {}
        
        except Exception as e:
            self.logger.error(f"Error getting meeting: {e}", exc_info=True)
            return {}
        
    def delete_meeting(self, chat_session_id: str) -> bool:
        """
        Delete meeting information for a chat session
        
        Args:
            chat_session_id: Chat session ID
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM ms_meetings WHERE chat_session_id = ?", (chat_session_id,))
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Meeting deleted for chat session {chat_session_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting meeting: {e}", exc_info=True)
            return False
    
    def get_ms_meeting_id(self, chat_session_id: str) -> Optional[str]:
        """
        Get Microsoft Graph meeting ID for a chat session
        
        Args:
            chat_session_id: Chat session ID
            
        Returns:
            Optional[str]: Microsoft Graph meeting ID or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT ms_meeting_id FROM ms_meetings WHERE chat_session_id = ?", (chat_session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return result[0]
            else:
                return None
        
        except Exception as e:
            self.logger.error(f"Error getting Microsoft meeting ID: {e}", exc_info=True)
            return None
    
    def get_online_meeting_url(self, chat_session_id: str) -> Optional[str]:
        """
        Get online meeting URL for a chat session
        
        Args:
            chat_session_id: Chat session ID
            
        Returns:
            Optional[str]: Online meeting URL or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT online_meeting_url FROM ms_meetings WHERE chat_session_id = ?", (chat_session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return result[0]
            else:
                return None
        
        except Exception as e:
            self.logger.error(f"Error getting online meeting URL: {e}", exc_info=True)
            return None
    
    def get_all_meetings(self) -> List[Dict[str, Any]]:
        """
        Get all meetings in the database
        
        Returns:
            List[Dict]: List of all meetings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT * FROM ms_meetings ORDER BY created_at DESC
            ''')
            
            results = cursor.fetchall()
            conn.close()
            
            meetings = []
            for result in results:
                meeting_data = dict(result)
                
                # Parse attendees JSON
                try:
                    meeting_data['attendees'] = json.loads(meeting_data.get('attendees', '[]'))
                except:
                    meeting_data['attendees'] = []
                
                meetings.append(meeting_data)
            
            self.logger.debug(f"Retrieved {len(meetings)} meetings")
            return meetings
        
        except Exception as e:
            self.logger.error(f"Error getting all meetings: {e}", exc_info=True)
            return []
    
    def get_user_meetings(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all meetings for a specific user
        
        Args:
            user_id: Microsoft user ID
            
        Returns:
            List[Dict]: List of user's meetings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT m.* FROM ms_meetings m
            JOIN ms_sessions s ON m.session_id = s.session_id
            WHERE s.user_id = ?
            ORDER BY m.created_at DESC
            ''', (user_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            meetings = []
            for result in results:
                meeting_data = dict(result)
                
                # Parse attendees JSON
                try:
                    meeting_data['attendees'] = json.loads(meeting_data.get('attendees', '[]'))
                except:
                    meeting_data['attendees'] = []
                
                meetings.append(meeting_data)
            
            self.logger.debug(f"Retrieved {len(meetings)} meetings for user {user_id}")
            return meetings
        
        except Exception as e:
            self.logger.error(f"Error getting user meetings: {e}", exc_info=True)
            return []
    
    def clear_expired_sessions(self, max_age_days: int = 7) -> int:
        """
        Clear expired sessions from the database
        
        Args:
            max_age_days: Maximum age of sessions in days
            
        Returns:
            int: Number of sessions deleted
        """
        try:
            import time
            from datetime import datetime, timedelta
            
            # Calculate cutoff timestamp
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            cutoff_timestamp = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Delete expired sessions
            cursor.execute('''
            DELETE FROM ms_sessions 
            WHERE created_at < ? AND expires_at < ?
            ''', (cutoff_timestamp, int(time.time())))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleared {deleted_count} expired sessions")
            return deleted_count
        
        except Exception as e:
            self.logger.error(f"Error clearing expired sessions: {e}", exc_info=True)
            return 0
