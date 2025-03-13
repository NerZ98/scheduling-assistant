import re
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import spacy
from spacy.matcher import Matcher

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
            # Load SpaCy model with transformer-based NER
            self.logger.info("Loading SpaCy transformer model...")
            self.nlp = spacy.load('en_core_web_trf')
            self.logger.info("SpaCy transformer model loaded successfully")
            
            # Log model details
            self.logger.debug(f"SpaCy model details: {self.nlp.meta}")
            self.logger.debug(f"Available NER labels: {self.nlp.get_pipe('ner').labels}")
        
        except Exception as e:
            self.logger.error(f"Failed to load models: {e}", exc_info=True)
            raise
        
        # Create a matcher for custom patterns
        self.logger.debug("Creating SpaCy matcher for custom patterns")
        self.matcher = Matcher(self.nlp.vocab)
        self._setup_custom_patterns()
    
    def _setup_custom_patterns(self):
        """
        Setup custom pattern matching for specific entities
        """
        try:
            self.logger.debug("Setting up custom entity patterns")
            
            # Date patterns
            date_patterns = [
                [{'LOWER': 'tomorrow'}],
                [{'LOWER': 'today'}],
                [{'LOWER': 'next'}, {'LOWER': {'IN': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']}}]
            ]
            self.logger.debug(f"Set up date patterns: {date_patterns}")
            
            # Time patterns
            time_patterns = [
                [{'SHAPE': 'dd'}, {'LOWER': {'IN': ['am', 'pm']}}],
                [{'SHAPE': 'dd'}, {'LOWER': ':'},  {'SHAPE': 'dd'}, {'LOWER': {'IN': ['am', 'pm']}}]
            ]
            self.logger.debug(f"Set up time patterns: {time_patterns}")
            
            # Duration patterns
            duration_patterns = [
                [{'SHAPE': 'dd'}, {'LOWER': {'IN': ['mins', 'min', 'minutes', 'hours', 'hour']}}]
            ]
            self.logger.debug(f"Set up duration patterns: {duration_patterns}")
            
            # Add patterns to matcher
            # self.matcher.add("DATE", date_patterns)
            # self.matcher.add("TIME", time_patterns)
            # self.matcher.add("DURATION", duration_patterns)
            
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
            self.logger.debug(f"Parsing date string: '{date_str}'")
            today = datetime.now()
            self.logger.debug(f"Current date: {today.strftime('%Y-%m-%d')}")
            
            date_mapping = {
                'today': today,
                'tomorrow': today + timedelta(days=1),
                'yesterday': today - timedelta(days=1)
            }
            
            # Handle next day of week
            next_day_match = re.match(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', date_str.lower())
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
            
            # Handle today, tomorrow, yesterday
            if date_str.lower() in date_mapping:
                self.logger.debug(f"Found relative date: '{date_str.lower()}'")
                parsed_date = date_mapping[date_str.lower()].strftime("%Y-%m-%d")
                self.logger.debug(f"Resolved '{date_str}' to date: {parsed_date}")
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
            self.logger.debug(f"No special date pattern matched, returning original: '{date_str}'")
            return date_str
        except Exception as e:
            self.logger.error(f"Error parsing date '{date_str}': {e}", exc_info=True)
            return date_str
        
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities using multiple strategies
        
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
        
        try:
            # Process text with SpaCy
            self.logger.debug("Processing text with SpaCy")
            doc = self.nlp(text)
            self.logger.debug(f"SpaCy entities found: {[(ent.text, ent.label_) for ent in doc.ents]}")
            
            # Time extraction - Do this FIRST to prevent time-only inputs being treated as names
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
            
            # Duration extraction - Do this SECOND to prevent duration-only inputs being treated as names
            self.logger.debug("Beginning duration extraction")
            duration_patterns = [
                # Patterns with units after number
                r'\b(\d+)\s*(?:minute|min|mins)\b',
                r'\b(\d+)\s*(?:hour|hr|hours)\b',
                
                # Patterns with 'for' before duration
                r'\bfor\s+(\d+)\s*(?:minute|min|mins)\b',
                r'\bfor\s+(\d+)\s*(?:hour|hr|hours)\b',
                
                # Less common variations
                r'\b(\d+)(?:m|min)\b',
                r'\b(\d+)(?:h|hr)\b'
            ]
            
            # Combine and find all matches
            full_duration_pattern = re.compile('|'.join(duration_patterns), re.IGNORECASE)
            duration_matches = full_duration_pattern.findall(text)
            self.logger.debug(f"Raw duration matches: {duration_matches}")
            
            # Process and format duration matches
            processed_durations = []
            for match in duration_matches:
                # Ensure we get the number (handle tuple results from regex)
                if isinstance(match, tuple):
                    # Take the first non-empty value
                    number = next((m for m in match if m), None)
                    self.logger.debug(f"Extracted duration number from tuple: {number}")
                else:
                    number = match
                    self.logger.debug(f"Extracted duration number: {number}")
                
                # Ensure number is not None
                if number:
                    # Check for specific hour patterns in the original text
                    hour_match = re.search(r'(\d+)\s*(?:hour|hr|hours|h)\b', text, re.IGNORECASE)
                    if hour_match and hour_match.group(1) == number:
                        processed_durations.append(f"{number} hours")
                        self.logger.debug(f"Identified as hours: {number} hours")
                    # Check for specific minute patterns in the original text
                    elif re.search(r'(\d+)\s*(?:minute|min|mins|m)\b', text, re.IGNORECASE):
                        processed_durations.append(f"{number} mins")
                        self.logger.debug(f"Identified as minutes: {number} mins")
                    # If no specific pattern found, check context
                    else:
                        if 'hour' in text.lower() or 'hr' in text.lower():
                            processed_durations.append(f"{number} hours")
                            self.logger.debug(f"Context suggests hours: {number} hours")
                        else:
                            processed_durations.append(f"{number} mins")
                            self.logger.debug(f"Defaulting to minutes: {number} mins")
            
            # Fallback to default pattern if no duration found
            if not processed_durations:
                self.logger.debug("No durations found with primary patterns, trying fallback")
                # Look for simple number followed by minutes or hours
                fallback_pattern = r'\b(\d+)\s*(?:mins?|minutes|hours?|hrs?)\b'
                fallback_matches = re.findall(fallback_pattern, text, re.IGNORECASE)
                self.logger.debug(f"Fallback duration matches: {fallback_matches}")
                
                for match in fallback_matches:
                    if 'hour' in text.lower() or 'hrs' in text.lower():
                        processed_durations.append(f"{match} hours")
                        self.logger.debug(f"Fallback identified hours: {match} hours")
                    else:
                        processed_durations.append(f"{match} mins")
                        self.logger.debug(f"Fallback identified minutes: {match} mins")
            
            entities['DURATION'] = processed_durations
            self.logger.info(f"Extracted durations: {entities['DURATION']}")
            
            # Date extraction
            self.logger.debug("Beginning date extraction")
            date_patterns = [
                r'\b(?:today|tomorrow|yesterday)\b',
                r'\bnext\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
                # Add new patterns for dates like "21st March"
                r'\b(?:\d{1,2})(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b',
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:\d{1,2})(?:st|nd|rd|th)?\b',
                r'\b(?:\d{1,2})(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(?:\d{1,2})(?:st|nd|rd|th)?\b'
            ]
            date_regex = re.compile('|'.join(date_patterns), re.IGNORECASE)
            date_matches = date_regex.findall(text)
            self.logger.debug(f"Raw date matches: {date_matches}")
            
            entities['DATE'] = [self.parse_date(date) for date in date_matches]
            self.logger.info(f"Extracted dates: {entities['DATE']}")
            
            # Check if we already identified time, duration, or date entities
            # If the entire input was captured as one of these entity types, skip attendee extraction
            if len(text.strip()) > 0:
                input_words = text.strip().split()
                
                # Check if the entire input is captured in TIME or DURATION
                if ((len(input_words) == 1 and (entities['TIME'] or entities['DURATION'])) or
                    (len(input_words) <= 2 and (entities['TIME'] or entities['DURATION'] or entities['DATE']))):
                    self.logger.debug("Input appears to be only time, duration, or date - skipping attendee extraction")
                    # The entire input was captured as time, duration, or date entity
                    # Skip attendee extraction for this input
                    return entities
            
            # Attendee extraction - with preprocessing to remove command words
            self.logger.debug("Beginning attendee extraction")

            # Preprocess text for attendee extraction
            attendee_text = text

            # List of command words to ignore in attendee extraction
            command_words = ['add', 'schedule', 'plan', 'create', 'set', 'arrange', 'invite', 'with', 'meeting', 'Add']

            # Replace command words with spaces
            for word in command_words:
                pattern = r'(?i)\b' + word + r'\b'
                attendee_text = re.sub(pattern, ' ', attendee_text)

            # Clean up multiple spaces
            attendee_text = re.sub(r'\s+', ' ', attendee_text).strip()

            self.logger.debug(f"Preprocessed text for attendee extraction: '{attendee_text}'")

            # Specifically parse comma-separated names or "and" separated names
            attendees = []

            # First, try to split by common separators (comma, and, &)
            if ',' in attendee_text or ' and ' in attendee_text or '&' in attendee_text:
                # Replace 'and' and '&' with commas for consistent parsing
                normalized_text = attendee_text.replace(' and ', ',').replace('&', ',')
                
                # Split by comma and clean each part
                name_parts = [part.strip() for part in normalized_text.split(',') if part.strip()]
                
                # Filter out empty parts and add to attendees
                for name in name_parts:
                    if name and len(name) > 1:  # Ensure name has some content
                        attendees.append(name)
                
                self.logger.debug(f"Extracted attendees from separators: {attendees}")

            # If separator parsing didn't work or as a fallback, try SpaCy NER
            if not attendees:
                # Process with SpaCy for attendees
                doc_for_attendees = self.nlp(attendee_text)
                
                # Try SpaCy NER for person names
                spacy_attendees = [ent.text for ent in doc_for_attendees.ents if ent.label_ == 'PERSON']
                self.logger.debug(f"SpaCy identified attendees: {spacy_attendees}")
                
                # Add to our attendees list
                attendees.extend(spacy_attendees)

            # If still no attendees found, try original text without preprocessing
            if not attendees:
                doc_original = self.nlp(text)
                spacy_attendees = [ent.text for ent in doc_original.ents if ent.label_ == 'PERSON']
                self.logger.debug(f"SpaCy identified attendees from original text: {spacy_attendees}")
                attendees.extend(spacy_attendees)

            # If still no attendees, try custom name extraction with stronger heuristics
            if not attendees and attendee_text.strip():
                self.logger.debug("No attendees found with SpaCy, trying custom pattern")
                
                # Look for capitalized words that might be names
                name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b'
                possible_names = re.findall(name_pattern, attendee_text, re.IGNORECASE)
                
                if not possible_names:
                    # If no capitalized names found, try the original text
                    possible_names = re.findall(name_pattern, text, re.IGNORECASE)
                    self.logger.debug(f"Looking for names in original text: {possible_names}")
                
                # As a last resort, check for any words that might be names
                if not possible_names:
                    # Split by space and consider individual words
                    words = [w.strip() for w in attendee_text.split() if len(w.strip()) > 1]
                    self.logger.debug(f"Considering individual words as potential names: {words}")
                    possible_names = words
                
                # Add possible names to attendees
                attendees.extend(possible_names)

            # Filter out query words and common words
            query_words = ['how', 'what', 'when', 'where', 'why', 'who', 'which', 'schedule', 'help', 'can']
            common_words = ['i', 'me', 'my', 'mine', 'you', 'your', 'he', 'she', 'his', 'her', 
                            'schedule', 'meeting', 'appointment', 'tomorrow', 'today', 
                            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                            'january', 'february', 'march', 'april', 'may', 'june', 'july', 
                            'august', 'september', 'october', 'november', 'december']

            attendees = [name for name in attendees 
                        if name.lower() not in [q.lower() for q in query_words + common_words + command_words]]

            # Remove duplicates while preserving order
            unique_attendees = []
            for attendee in attendees:
                if attendee not in unique_attendees:
                    unique_attendees.append(attendee)

            entities['ATTENDEE'] = unique_attendees
            self.logger.info(f"Final extracted attendees: {entities['ATTENDEE']}")
            
            # Log the complete extraction results
            self.logger.info("Entity extraction completed successfully")
            self.logger.debug(f"Complete extracted entities: {entities}")
            
            return entities
        
        except Exception as e:
            self.logger.error(f"Error during entity extraction: {e}", exc_info=True)
            raise
        
    def validate_attendees(self, attendees: List[str]) -> tuple[List[str], List[str]]:
        """
        Validate attendees against the contacts database
        
        Args:
            attendees (List[str]): List of attendee names to validate
            
        Returns:
            Tuple[List[str], List[str]]: Valid attendees and invalid attendees
        """
        valid_attendees = []
        invalid_attendees = []
        
        for attendee in attendees:
            # Skip attendees that already have emails in their name
            if '(' in attendee and '@' in attendee and ')' in attendee:
                valid_attendees.append(attendee)
                continue
            
            # Search for contacts matching this name
            contacts = self.contact_db.find_contacts_by_name(attendee)
            
            if contacts:
                valid_attendees.append(attendee)
            else:
                # Try fuzzy matching - check if any contact name is similar to this attendee
                all_contacts = self.contact_db.get_all_contacts()
                found_match = False
                
                for contact in all_contacts:
                    full_name = f"{contact['first_name']} {contact['last_name']}".lower()
                    attendee_lower = attendee.lower()
                    
                    # Check if name parts are similar
                    if (attendee_lower in full_name or
                        attendee_lower in contact['first_name'].lower() or
                        attendee_lower in contact['last_name'].lower() or
                        # Check if first few letters match
                        (len(attendee_lower) >= 3 and (
                            contact['first_name'].lower().startswith(attendee_lower[:3]) or
                            contact['last_name'].lower().startswith(attendee_lower[:3])
                        ))):
                        
                        # Add the correct name instead of the misspelled one
                        correct_name = f"{contact['first_name']} {contact['last_name']}"
                        valid_attendees.append(correct_name)
                        found_match = True
                        self.logger.info(f"Found fuzzy match for '{attendee}': '{correct_name}'")
                        break
                
                if not found_match:
                    invalid_attendees.append(attendee)
        
        return valid_attendees, invalid_attendees