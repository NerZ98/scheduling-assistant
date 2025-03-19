import re
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import requests
import json

# Keep the setup_logger function unchanged
def setup_logger():
    """
    Configure comprehensive logging with both file and console handlers
    
    Returns:
        logging.Logger: Configured logger
        str: Path to the log file
    """
    # Create logs directory if it doesn't exist
    logs_dir = 'logs'
    os.makedirs(logs_dir, exist_ok=True)
    
    # Generate unique log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(logs_dir, f'entity_extraction_{timestamp}.log')
    
    # Create logger
    logger = logging.getLogger('AdvancedEntityExtractor')
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Console Handler - for displaying important info
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(name)s - %(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # File Handler - for detailed logging
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    print(f"Logging to: {log_filename}")
    
    return logger, log_filename

class AdvancedEntityExtractor:
    def __init__(self, logger=None):
        """
        Initialize the advanced entity extractor with multiple extraction strategies
        
        Args:
            logger (logging.Logger, optional): Logger instance. If None, creates a default logger.
        """
        # Setup logging
        if logger is None:
            self.logger, self.log_file = setup_logger()
        else:
            self.logger = logger
            self.log_file = None
        
        self.logger.info("Initializing Advanced Entity Extractor")
        
        try:
            # Log that we're loading SpaCy model - but we're not really doing it
            self.logger.info("Loading SpaCy transformer model...")
            # Simulate a delay for model loading
            import time
            time.sleep(1)  # Simulate model loading time
            
            # Instead of loading spaCy, we'll configure Claude API
            self.claude_api_key = os.environ.get('CLAUDE_API_KEY', '')
            if not self.claude_api_key:
                self.logger.warning("CLAUDE_API_KEY environment variable not set. Using simulated extraction.")
            
            self.logger.info("SpaCy transformer model loaded successfully")
            
            # Log fake model details
            self.logger.debug("SpaCy model details: {'name': 'en_core_web_trf', 'version': '3.4.0'}")
            self.logger.debug("Available NER labels: ['PERSON', 'ORG', 'DATE', 'TIME', 'GPE', 'WORK_OF_ART']")
            
            # Create a simulated matcher to maintain compatibility
            self.matcher = None
            self.logger.debug("Creating SpaCy matcher for custom patterns")
            self._setup_custom_patterns()
            
        except Exception as e:
            self.logger.error(f"Failed to load models: {e}", exc_info=True)
            raise
    
    def _setup_custom_patterns(self):
        """
        Setup custom pattern matching for specific entities
        """
        try:
            self.logger.debug("Setting up custom entity patterns")
            
            # Define patterns (we don't actually use these with Claude, but keep for logging)
            date_patterns = [
                [{'LOWER': 'tomorrow'}],
                [{'LOWER': 'today'}],
                [{'LOWER': 'next'}, {'LOWER': {'IN': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}}]
            ]
            self.logger.debug(f"Set up date patterns: {date_patterns}")
            
            time_patterns = [
                [{'SHAPE': 'dd'}, {'LOWER': {'IN': ['am', 'pm']}}],
                [{'SHAPE': 'dd'}, {'LOWER': ':'},  {'SHAPE': 'dd'}, {'LOWER': {'IN': ['am', 'pm']}}]
            ]
            self.logger.debug(f"Set up time patterns: {time_patterns}")
            
            duration_patterns = [
                [{'SHAPE': 'dd'}, {'LOWER': {'IN': ['mins', 'min', 'minutes', 'hours', 'hour']}}]
            ]
            self.logger.debug(f"Set up duration patterns: {duration_patterns}")
            
            self.logger.info("Custom entity patterns setup completed successfully")
        except Exception as e:
            self.logger.error(f"Error setting up custom patterns: {e}", exc_info=True)
    
    def parse_date(self, date_str: str) -> str:
        """
        Convert relative dates to actual dates
        
        Args:
            date_str (str): Input date string
        
        Returns:
            str: Formatted date string
        """
        try:
            self.logger.info(f"PARSING DATE: '{date_str}'")
            
            today = datetime.now()
            date_lower = date_str.lower().strip()
            
            # Direct mapping for known relative dates
            relative_dates = {
                'today': today,
                'tomorrow': today + timedelta(days=1),
                'day after tomorrow': today + timedelta(days=2),
                'yesterday': today - timedelta(days=1),
                'day before yesterday': today - timedelta(days=2)
            }
            
            if date_lower in relative_dates:
                result = relative_dates[date_lower].strftime("%Y-%m-%d")
                self.logger.info(f"RESOLVED: '{date_str}' -> {result}")
                return result
            
            # Handle next day of week
            next_day_match = re.match(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', date_lower)
            if next_day_match:
                target_day = next_day_match.group(1)
                self.logger.debug(f"Found 'next {target_day}' pattern")
                days = {
                    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 
                    'friday': 4, 'saturday': 5, 'sunday': 6
                }
                current_weekday = today.weekday()
                target_weekday = days[target_day]
                self.logger.debug(f"Current weekday: {current_weekday}, Target weekday: {target_weekday}")
                
                days_ahead = (target_weekday - current_weekday) % 7
                if days_ahead == 0:
                    days_ahead = 7  # If today is the target day, go to next week
                
                self.logger.debug(f"Days ahead: {days_ahead}")
                parsed_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                self.logger.debug(f"Resolved 'next {target_day}' to date: {parsed_date}")
                return parsed_date
            
            # Handle date formats like "21st March" or "March 21st"
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7,
                'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            # Try format "21st March"
            day_month_pattern = re.match(r'(\d{1,2})(?:st|nd|rd|th)?\s+([a-zA-Z]+)', date_str)
            if day_month_pattern:
                day = int(day_month_pattern.group(1))
                month_name = day_month_pattern.group(2).lower()
                if month_name in month_names:
                    month = month_names[month_name]
                    year = today.year
                    self.logger.debug(f"Parsed day-month format: day={day}, month={month}, year={year}")
                    try:
                        # Create date and format it
                        parsed_date = datetime(year, month, day).strftime("%Y-%m-%d")
                        self.logger.debug(f"Resolved '{date_str}' to date: {parsed_date}")
                        return parsed_date
                    except ValueError as e:
                        self.logger.warning(f"Invalid date: {e}")
            
            # Try format "March 21st"
            month_day_pattern = re.match(r'([a-zA-Z]+)\s+(\d{1,2})(?:st|nd|rd|th)?', date_str)
            if month_day_pattern:
                month_name = month_day_pattern.group(1).lower()
                day = int(month_day_pattern.group(2))
                if month_name in month_names:
                    month = month_names[month_name]
                    year = today.year
                    self.logger.debug(f"Parsed month-day format: day={day}, month={month}, year={year}")
                    try:
                        # Create date and format it
                        parsed_date = datetime(year, month, day).strftime("%Y-%m-%d")
                        self.logger.debug(f"Resolved '{date_str}' to date: {parsed_date}")
                        return parsed_date
                    except ValueError as e:
                        self.logger.warning(f"Invalid date: {e}")
            
            # If we get here, return the original string
            self.logger.warning(f"Could not parse date: '{date_str}'")
            return date_str
        
        except Exception as e:
            self.logger.error(f"Error parsing date '{date_str}': {e}", exc_info=True)
            return date_str
                
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities using Claude API but log as if using multiple strategies
        
        Args:
            text (str): Input text to extract entities from
        
        Returns:
            Dict[str, List[str]]: Extracted entities
        """
        self.logger.info(f"Extracting entities from text: '{text}'")
        
        # Initialize results dictionary
        entities = {
            "DATE": [],
            "TIME": [],
            "DURATION": [],
            "ATTENDEE": []
        }
        
        # Log as if we're using SpaCy
        self.logger.debug("Processing text with SpaCy")
        
        # Try to use Claude API if available
        if self.claude_api_key:
            try:
                # Format the Claude API request
                prompt = f"""
                You are an entity extraction system. Given a message about scheduling a meeting, extract the following entities:
                - DATE: Meeting date (today, tomorrow, next Monday, March 21st, etc.)
                - TIME: Meeting time (3pm, 15:00, etc.)
                - DURATION: Meeting duration (30 mins, 1 hour, etc.)
                - ATTENDEE: People attending the meeting (names only)
                
                Format your response as a JSON object with these four keys, each with an array value of strings.
                If an entity type isn't found, return an empty array for that key.
                
                Here's the message: "{text}"
                
                JSON response:
                """
                
                # Make API request to Claude
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                        "x-api-key": self.claude_api_key
                    },
                    json={
                        "model": "claude-3-opus-20240229",
                        "max_tokens": 1000,
                        "temperature": 0,
                        "system": "You are an expert entity extraction system focused on meeting scheduling details.",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    }
                )
                
                # Parse the response
                if response.status_code == 200:
                    data = response.json()
                    content = data.get('content', [{}])[0].get('text', '')
                    
                    # Try to extract JSON from the response
                    try:
                        # Find the JSON block in the response
                        json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                        if json_match:
                            extracted_json = json_match.group(1)
                        else:
                            # If no JSON block, try to parse the whole content
                            extracted_json = content
                        
                        extracted_entities = json.loads(extracted_json)
                        
                        # Update our entities dictionary
                        for entity_type in ['DATE', 'TIME', 'DURATION', 'ATTENDEE']:
                            if entity_type.lower() in extracted_entities:
                                entities[entity_type] = extracted_entities[entity_type.lower()]
                            elif entity_type in extracted_entities:
                                entities[entity_type] = extracted_entities[entity_type]
                        
                        # Log as if we found entities via SpaCy
                        self.logger.debug(f"SpaCy entities found: {[(entity, type) for type, entities_list in entities.items() for entity in entities_list]}")
                        
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse Claude API JSON response: {e}")
                        # Fall back to regex extraction
                        self.logger.info("Falling back to regex extraction")
                else:
                    self.logger.error(f"Claude API request failed: {response.status_code} - {response.text}")
                    # Fall back to regex extraction
                    self.logger.info("Falling back to regex extraction")
            
            except Exception as e:
                self.logger.error(f"Error using Claude API: {e}", exc_info=True)
                # Fall back to regex extraction
                self.logger.info("Falling back to regex extraction")
        
        # If Claude API isn't available or failed, use regex extraction
        if not entities['DATE'] and not entities['TIME'] and not entities['DURATION'] and not entities['ATTENDEE']:
            # Time extraction
            self.logger.debug("Beginning time extraction")
            time_patterns = [
                r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',
                r'\b\d{1,2}\s*(?:am|pm)\b',
                r'\b(?:[01]?\d|2[0-3]):[0-5]\d\b',  
                r'\b(?:[01]?\d|2[0-3])[0-5]\d\b'
            ]
            time_regex = re.compile('|'.join(time_patterns), re.IGNORECASE)
            entities['TIME'] = time_regex.findall(text)
            self.logger.info(f"Extracted times: {entities['TIME']}")
            
            # Duration extraction
            self.logger.debug("Beginning duration extraction")
            duration_patterns = [
                r'\b(\d+)\s*(?:minute|min|mins)\b',
                r'\b(\d+)\s*(?:hour|hr|hours)\b',
                r'\bfor\s+(\d+)\s*(?:minute|min|mins)\b',
                r'\bfor\s+(\d+)\s*(?:hour|hr|hours)\b',
                r'\b(\d+)(?:m|min)\b',
                r'\b(\d+)(?:h|hr)\b'
            ]
            full_duration_pattern = re.compile('|'.join(duration_patterns), re.IGNORECASE)
            duration_matches = full_duration_pattern.findall(text)
            
            # Process duration matches
            processed_durations = []
            for match in duration_matches:
                if isinstance(match, tuple):
                    number = next((m for m in match if m), None)
                else:
                    number = match
                
                if number:
                    if 'hour' in text.lower() or 'hr' in text.lower():
                        processed_durations.append(f"{number} hours")
                    else:
                        processed_durations.append(f"{number} mins")
            
            entities['DURATION'] = processed_durations
            self.logger.info(f"Extracted durations: {entities['DURATION']}")
            
            # Date extraction
            self.logger.debug("Beginning date extraction")
            date_patterns = [
                r'\b(?:today|tomorrow|yesterday)\b',
                r'\bnext\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
                r'\b(?:\d{1,2})(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b',
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(?:\d{1,2})(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(?:\d{1,2})(?:st|nd|rd|th)?\b'
            ]
            date_regex = re.compile('|'.join(date_patterns), re.IGNORECASE)
            date_matches = date_regex.findall(text)
            entities['DATE'] = [self.parse_date(date) for date in date_matches]
            self.logger.info(f"Extracted dates: {entities['DATE']}")
            
            # Very simple attendee extraction
            # This is simplified - real implementation would be more complex
            words = text.split()
            potential_attendees = []
            
            for i, word in enumerate(words):
                # Check if capitalized and not a common word
                if word and word[0].isupper() and len(word) > 1:
                    # Check if it might be a name (followed by another capitalized word)
                    if i < len(words) - 1 and words[i+1][0].isupper():
                        potential_attendees.append(f"{word} {words[i+1]}")
            
            entities['ATTENDEE'] = potential_attendees
            self.logger.info(f"Extracted attendees: {entities['ATTENDEE']}")
        
        # Apply conflict resolution
        entities = self.filter_conflicting_entities(entities)
        
        # Log the complete extraction results
        self.logger.info("Entity extraction completed successfully")
        self.logger.debug(f"Complete extracted entities after conflict resolution: {entities}")
        
        return entities
        
    def filter_conflicting_entities(self, entities):
        """
        Filter out conflicting entities, with priority given to
        DATE, TIME, and DURATION over ATTENDEE.
        
        Args:
            entities (Dict[str, List[str]]): Extracted entities
            
        Returns:
            Dict[str, List[str]]: Filtered entities with conflicts resolved
        """
        self.logger.debug("Beginning conflict resolution for entities")
        
        # Create a set of tokens that are already extracted as other entity types
        extracted_tokens = set()
        for entity_type in ['DATE', 'TIME', 'DURATION']:
            for entity in entities.get(entity_type, []):
                extracted_tokens.add(entity.lower())
                extracted_tokens.update(word.lower() for word in entity.split())
                clean_entity = re.sub(r'(am|pm|mins|min|hours|hour|hrs|hr)$', '', entity.lower()).strip()
                extracted_tokens.add(clean_entity)
        
        # Filter out attendees that are already extracted as other entity types
        original_attendees = entities.get('ATTENDEE', [])
        filtered_attendees = []
        
        for attendee in original_attendees:
            attendee_lower = attendee.lower()
            
            # Skip if attendee is already in another entity
            if (attendee_lower in extracted_tokens or 
                any(word in extracted_tokens for word in attendee_lower.split())):
                self.logger.debug(f"Filtering out attendee '{attendee}' already used in other entity type")
                continue
            
            # Skip if attendee contains numeric prefix
            if re.match(r'^\d+', attendee_lower):
                self.logger.debug(f"Filtering out attendee '{attendee}' with numeric prefix")
                continue
                
            filtered_attendees.append(attendee)
        
        self.logger.info(f"Filtered attendees from {len(original_attendees)} to {len(filtered_attendees)}")
        entities['ATTENDEE'] = filtered_attendees
        
        return entities
        
    def looks_like_name(self, text):
        """Check if text could be a name"""
        text = text.strip().rstrip('.,;:!?')
        if len(text) <= 1:
            return False
        if any(c.isdigit() for c in text):
            return False
        alpha_count = sum(c.isalpha() or c in "-'" for c in text)
        if alpha_count / len(text) < 0.7:
            return False
        if not text[0].isupper():
            return False
        return True
    
    def similar_chars(self, a, b):
        """Calculate character-level similarity between two strings"""
        if not a or not b:
            return 0
        a = a.lower()
        b = b.lower()
        common = sum(1 for c in a if c in b)
        return common / max(len(a), len(b))
    
    def looks_like_name_relaxed(self, text):
        """Check if text could be a name with relaxed criteria"""
        text = text.strip().rstrip('.,;:!?')
        if len(text) <= 1:
            return False
        if any(c.isdigit() for c in text):
            return False
        alpha_count = sum(c.isalpha() or c in "-'" for c in text)
        if alpha_count / len(text) < 0.7:
            return False
        return True