import msal
import requests
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

class GraphClient:
    """Microsoft Graph API client for calendar and meeting operations"""
    
    def __init__(self, config, logger=None):
        """
        Initialize Microsoft Graph client
        
        Args:
            config: Application configuration containing Microsoft Graph settings
            logger: Logger instance
        """
        self.client_id = config.MICROSOFT_CLIENT_ID
        self.client_secret = config.MICROSOFT_CLIENT_SECRET
        
        # Handle tenant ID configuration
        tenant_id = getattr(config, 'MICROSOFT_TENANT_ID', None)
        if tenant_id and tenant_id != 'common':
            # Use specific tenant ID
            self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        else:
            # Use configured authority (defaults to 'common')
            self.authority = config.MICROSOFT_AUTHORITY
        
        self.redirect_uri = config.MICROSOFT_REDIRECT_URI
        self.scope = config.MICROSOFT_SCOPE.split()
        
        # Setup logging
        self.logger = logger or logging.getLogger('GraphClient')
        
        # Log configuration for debugging
        self.logger.info(f"Initializing Microsoft Graph client")
        self.logger.info(f"Authority: {self.authority}")
        self.logger.info(f"Redirect URI: {self.redirect_uri}")
        self.logger.info(f"Scope: {self.scope}")
        
        # Microsoft Graph API endpoints
        self.base_url = "https://graph.microsoft.com/v1.0"
        
        # Token cache for tracking user tokens
        self.token_cache = {}
        
        # Initialize MSAL application
        # Using PublicClientApplication for browser-based flow
        try:
            self.app = msal.PublicClientApplication(
                client_id=self.client_id,
                authority=self.authority
            )
            self.logger.info("MSAL application initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize MSAL application: {e}", exc_info=True)
            raise
    
    def get_auth_url(self) -> Tuple[str, str, str]:
        """
        Generate authorization URL for Microsoft Graph API with PKCE
        
        Returns:
            Tuple: (auth_url, state, code_verifier)
        """
        self.logger.info("Generating Microsoft Graph authorization URL")
        
        # Generate a random state value for CSRF protection
        state = str(uuid.uuid4())
        
        # Generate the authorization URL
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scope,
            state=state,
            redirect_uri=self.redirect_uri
        )
        
        # This simple implementation doesn't need code_verifier, but we return a placeholder 
        # to maintain the interface expected by the application
        code_verifier = "not_used_in_this_flow"
        
        self.logger.debug(f"Generated auth URL (truncated): {auth_url[:100]}...")
        return auth_url, state, code_verifier
    
    def get_token_from_code(self, auth_code: str, code_verifier: str = None) -> Dict[str, Any]:
        """
        Exchange authorization code for access token
        
        Args:
            auth_code: Authorization code from callback
            code_verifier: Optional PKCE code verifier
            
        Returns:
            Dict: Token information including access_token and refresh_token
        """
        self.logger.info("Acquiring token from authorization code")
        
        try:
            result = self.app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=self.scope,
                redirect_uri=self.redirect_uri
            )
            
            if "error" in result:
                self.logger.error(f"Error acquiring token: {result.get('error')}: {result.get('error_description', 'Unknown error')}")
                return {
                    "success": False,
                    "error": result.get('error'),
                    "error_description": result.get('error_description')
                }
            
            # Extract user info from claims
            user_id = result.get("id_token_claims", {}).get("oid") or result.get("id_token_claims", {}).get("sub")
            
            # Store token in cache
            self.token_cache[user_id] = {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_in": result.get("expires_in", 3600),
                "expires_at": datetime.now() + timedelta(seconds=result.get("expires_in", 3600))
            }
            
            self.logger.info("Token acquired successfully")
            return {
                "success": True,
                "user_id": user_id,
                "expires_in": result.get("expires_in", 3600)
            }
        
        except Exception as e:
            self.logger.error(f"Exception acquiring token: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_token_for_user(self, user_id):
        """
        Get a valid token for a specific user, refreshing if necessary
        
        Parameters:
        - user_id: The user's ID
        
        Returns:
        - Access token or None if no valid token available
        """
        self.logger.debug(f"Getting token for user_id: {user_id}")
        
        # Check if we have a token for this user
        if user_id not in self.token_cache:
            self.logger.error(f"No token found in cache for user_id: {user_id}")
            return None
        
        token_info = self.token_cache[user_id]
        
        # Check if token is expired or about to expire
        now = datetime.now()
        if now >= token_info["expires_at"] - timedelta(minutes=5):
            self.logger.info(f"Token expired or about to expire. Attempting refresh.")
            # Token is expired, try to refresh
            if "refresh_token" in token_info:
                result = self.app.acquire_token_by_refresh_token(
                    refresh_token=token_info["refresh_token"],
                    scopes=self.scope
                )
                
                if "access_token" in result:
                    # Update token in cache
                    token_info["access_token"] = result["access_token"]
                    token_info["refresh_token"] = result.get("refresh_token", token_info["refresh_token"])
                    token_info["expires_in"] = result.get("expires_in", 3600)
                    token_info["expires_at"] = now + timedelta(seconds=result.get("expires_in", 3600))
                    
                    self.logger.info(f"Token refreshed successfully")
                    return token_info["access_token"]
                else:
                    # Refresh failed
                    self.logger.error(f"Token refresh failed: {result.get('error', 'Unknown error')}")
                    return None
            else:
                # No refresh token
                self.logger.error(f"No refresh token available for user_id: {user_id}")
                return None
        
        # Token is still valid
        return token_info["access_token"]
    
    def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get current user information
        
        Args:
            access_token: Access token for Microsoft Graph API
            
        Returns:
            Dict: User information
        """
        self.logger.info("Getting user information")
        
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.base_url}/me",
                headers=headers
            )
            
            if response.status_code == 200:
                user_info = response.json()
                self.logger.debug(f"Retrieved user info: {user_info.get('displayName', 'Unknown')}")
                return user_info
            else:
                self.logger.error(f"Error getting user info: {response.status_code} - {response.text}")
                return {}
        
        except Exception as e:
            self.logger.error(f"Exception getting user info: {e}", exc_info=True)
            return {}
    
    def create_meeting(self, user_id: str, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a meeting/event in user's calendar with online meeting link
        
        Args:
            user_id: User ID for token lookup
            meeting_data: Meeting information including subject, attendees, start/end times
            
        Returns:
            Dict: Created meeting information
        """
        self.logger.info(f"Creating meeting: {meeting_data.get('subject', 'Untitled')}")
        
        try:
            # Get token for user
            access_token = self.get_token_for_user(user_id)
            if not access_token:
                return {
                    "success": False,
                    "error": "No valid token available"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Prepare attendees list
            attendees = []
            for email in meeting_data.get('attendees', []):
                attendees.append({
                    "emailAddress": {
                        "address": email
                    },
                    "type": "required"
                })
            
            # Format start/end times
            start_time = f"{meeting_data['date']}T{meeting_data['time']}"
            start_datetime = datetime.fromisoformat(start_time)
            duration_minutes = meeting_data.get('duration_minutes', 30)
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            end_time = end_datetime.isoformat()
            
            # Format request body
            body = {
                "subject": meeting_data.get('subject', 'Meeting'),
                "body": {
                    "contentType": "HTML",
                    "content": meeting_data.get('body', '')
                },
                "start": {
                    "dateTime": start_time,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "UTC"
                },
                "location": {
                    "displayName": meeting_data.get('location', 'Online')
                },
                "attendees": attendees,
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness"
            }
            
            self.logger.debug(f"Meeting request payload: {json.dumps(body, default=str)}")
            
            response = requests.post(
                f"{self.base_url}/me/events",
                headers=headers,
                data=json.dumps(body)
            )
            
            if response.status_code in [200, 201]:
                created_meeting = response.json()
                self.logger.info(f"Meeting created successfully: {created_meeting.get('id', 'Unknown ID')}")
                return created_meeting
            else:
                self.logger.error(f"Error creating meeting: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text}"
                }
        
        except Exception as e:
            self.logger.error(f"Exception creating meeting: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_meeting(self, user_id: str, meeting_id: str, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing meeting/event
        
        Args:
            user_id: User ID for token lookup
            meeting_id: Microsoft Graph meeting/event ID
            meeting_data: Updated meeting information
            
        Returns:
            Dict: Updated meeting information
        """
        self.logger.info(f"Updating meeting: {meeting_id}")
        
        try:
            # Get token for user
            access_token = self.get_token_for_user(user_id)
            if not access_token:
                return {
                    "success": False,
                    "error": "No valid token available"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Format request body with only fields to update
            body = {}
            
            if 'subject' in meeting_data:
                body['subject'] = meeting_data['subject']
            
            if 'body' in meeting_data:
                body['body'] = {
                    "contentType": "HTML",
                    "content": meeting_data['body']
                }
            
            if 'start_time' in meeting_data:
                body['start'] = {
                    "dateTime": meeting_data['start_time'],
                    "timeZone": "UTC"
                }
            
            if 'end_time' in meeting_data:
                body['end'] = {
                    "dateTime": meeting_data['end_time'],
                    "timeZone": "UTC"
                }
            
            if 'location' in meeting_data:
                body['location'] = {
                    "displayName": meeting_data['location']
                }
            
            if 'attendees' in meeting_data:
                attendees = []
                for email in meeting_data['attendees']:
                    attendees.append({
                        "emailAddress": {
                            "address": email
                        },
                        "type": "required"
                    })
                body['attendees'] = attendees
            
            response = requests.patch(
                f"{self.base_url}/me/events/{meeting_id}",
                headers=headers,
                data=json.dumps(body)
            )
            
            if response.status_code == 200:
                updated_meeting = response.json()
                self.logger.info(f"Meeting updated successfully: {meeting_id}")
                return updated_meeting
            else:
                self.logger.error(f"Error updating meeting: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text}"
                }
        
        except Exception as e:
            self.logger.error(f"Exception updating meeting: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_meeting(self, user_id: str, meeting_id: str) -> bool:
        """
        Delete a meeting/event
        
        Args:
            user_id: User ID for token lookup
            meeting_id: Microsoft Graph meeting/event ID
            
        Returns:
            bool: True if deleted successfully, False otherwise
        """
        self.logger.info(f"Deleting meeting: {meeting_id}")
        
        try:
            # Get token for user
            access_token = self.get_token_for_user(user_id)
            if not access_token:
                return False
            
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            
            response = requests.delete(
                f"{self.base_url}/me/events/{meeting_id}",
                headers=headers
            )
            
            if response.status_code == 204:
                self.logger.info(f"Meeting deleted successfully: {meeting_id}")
                return True
            else:
                self.logger.error(f"Error deleting meeting: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            self.logger.error(f"Exception deleting meeting: {e}", exc_info=True)
            return False
    
    def format_date_time(self, date_str: str, time_str: str, duration_str: str) -> Tuple[str, str]:
        """
        Format date, time and duration into ISO format for Graph API
        
        Args:
            date_str: Date string (e.g. "2023-03-15")
            time_str: Time string (e.g. "3pm" or "15:00")
            duration_str: Duration string (e.g. "30 mins" or "1 hour")
            
        Returns:
            Tuple[str, str]: Formatted start and end times in ISO format
        """
        try:
            # Parse date
            if "-" in date_str:
                # Already in YYYY-MM-DD format
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                # Try other common formats
                date_formats = ["%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"Could not parse date: {date_str}")
            
            # Parse time
            time_str = time_str.lower().strip()
            
            if ":" in time_str:
                # Handle format like "3:00pm"
                if "pm" in time_str or "am" in time_str:
                    time_obj = datetime.strptime(time_str, "%I:%M%p")
                else:
                    time_obj = datetime.strptime(time_str, "%H:%M")
            else:
                # Handle format like "3pm"
                if "pm" in time_str or "am" in time_str:
                    time_obj = datetime.strptime(time_str, "%I%p")
                else:
                    time_obj = datetime.strptime(time_str, "%H")
            
            # Combine date and time
            start_datetime = datetime.combine(date_obj.date(), time_obj.time())
            
            # Parse duration
            duration_parts = duration_str.lower().strip().split()
            duration_value = int(duration_parts[0])
            
            if any(unit in duration_parts[1] for unit in ["hour", "hr", "hours", "hrs"]):
                end_datetime = start_datetime + timedelta(hours=duration_value)
            else:
                # Assume minutes if not hours
                end_datetime = start_datetime + timedelta(minutes=duration_value)
            
            # Format to ISO 8601 for Graph API
            start_time_iso = start_datetime.isoformat() + "Z"  # Add Z for UTC
            end_time_iso = end_datetime.isoformat() + "Z"
            
            return start_time_iso, end_time_iso
        
        except Exception as e:
            self.logger.error(f"Error formatting date/time: {e}", exc_info=True)
            # Return default 1-hour meeting from now
            now = datetime.utcnow()
            start_time_iso = now.isoformat() + "Z"
            end_time_iso = (now + timedelta(hours=1)).isoformat() + "Z"
            return start_time_iso, end_time_iso
    
    def extract_emails_from_attendees(self, attendees: List[str]) -> List[str]:
        """
        Extract email addresses from attendee strings
        
        Args:
            attendees: List of attendee strings (e.g. "John Smith (john@example.com)")
            
        Returns:
            List[str]: List of email addresses
        """
        emails = []
        
        for attendee in attendees:
            # Try to extract email from format "Name (email@example.com)"
            import re
            email_match = re.search(r'\(([^)]+@[^)]+)\)', attendee)
            
            if email_match:
                emails.append(email_match.group(1))
        
        return emails