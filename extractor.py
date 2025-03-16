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
        
        # Define time/date/duration keywords to exclude from attendees
        time_date_keywords = [
            'am', 'pm', 'hour', 'hours', 'hr', 'hrs', 'minute', 'minutes', 'min', 'mins', 
            'second', 'seconds', 'sec', 'secs', 'day', 'days', 'week', 'weeks', 'month', 'months',
            'year', 'years', 'today', 'tomorrow', 'yesterday', 'morning', 'afternoon', 'evening',
            'night', 'noon', 'midnight', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
            'saturday', 'sunday', 'january', 'february', 'march', 'april', 'may', 'june', 'july',
            'august', 'september', 'october', 'november', 'december', 'jan', 'feb', 'mar', 'apr',
            'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
        ]
        
        # Additional patterns to detect time and duration strings
        time_duration_patterns = [
            r'^\d+\s*(?:mins|min|minutes|m|hours|hour|hrs|hr)$',  # e.g., "15mins", "2hours" 
            r'^\d+(?::\d+)?\s*(?:am|pm)?$',  # e.g., "2pm", "2:30", "14:30"
            r'^\d+\s*(?:am|pm)$'  # e.g., "2pm", "10am"
        ]

        # Compile the patterns
        time_duration_regex = [re.compile(pattern, re.IGNORECASE) for pattern in time_duration_patterns]
        
        try:
            # Process text with SpaCy
            self.logger.debug("Processing text with SpaCy")
            doc = self.nlp(text)
            self.logger.debug(f"SpaCy entities found: {[(ent.text, ent.label_) for ent in doc.ents]}")
            
            person_entities = [ent.text for ent in doc.ents if ent.label_ == 'PERSON']
            self.logger.debug(f"SpaCy identified person entities: {person_entities}")
            
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
                    
                    # Apply conflict resolution before returning
                    entities = self.filter_conflicting_entities(entities)
                    
                    self.logger.info("Entity extraction completed successfully")
                    self.logger.debug(f"Complete extracted entities after conflict resolution: {entities}")
                    
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

            # Extract individual names - split by common separators
            attendees = []
            
            # First, replace 'and' and '&' with commas for consistent parsing
            normalized_text = attendee_text.replace(' and ', ',').replace('&', ',')
            
            # Split by comma to get name segments
            name_segments = [segment.strip() for segment in normalized_text.split(',') if segment.strip()]
            
            # For each segment, split by spaces to get individual names
            for segment in name_segments:
                # Split the segment by space to get individual names
                individual_names = segment.split()
                # Add each individual name as a separate attendee
                for name in individual_names:
                    if name and len(name) > 1:  # Ensure name has some content and length
                        attendees.append(name)

            # If no attendees found, try SpaCy NER as fallback
            if not attendees:
                # Process with SpaCy for attendees
                doc_for_attendees = self.nlp(attendee_text)
                
                # Try SpaCy NER for person names
                spacy_attendees = [ent.text for ent in doc_for_attendees.ents if ent.label_ == 'PERSON']
                self.logger.debug(f"SpaCy identified attendees: {spacy_attendees}")
                
                # For each SpaCy attendee, split by spaces as well
                for spacy_name in spacy_attendees:
                    name_parts = spacy_name.split()
                    for part in name_parts:
                        if part and len(part) > 1:
                            attendees.append(part)

            # Apply improved filtering to remove time/date/duration values from attendees
            # Filter out query words, common words, time/date terms, and numerical values
            query_words = ['how', 'what', 'when', 'where', 'why', 'who', 'which', 'schedule', 'help', 'can']
            # Add a much more comprehensive list of common words to filter out
            common_words = [
                # Original common words
                'i', 'me', 'my', 'mine', 'you', 'your', 'he', 'she', 'his', 'her', 
                'schedule', 'meeting', 'appointment', 'tomorrow', 'today',
                
                # Common verbs
                'need', 'meet', 'discuss', 'plan', 'arrange', 'set', 'have', 'want', 'would', 'like',
                'call', 'talk', 'speak', 'chat', 'sync', 'catch', 'get', 'make', 'put', 'take',
                'create', 'organize', 'coordinate', 'establish', 'setup', 'schedule',
                
                # Common nouns related to meetings
                'meeting', 'call', 'session', 'sync', 'discussion', 'conversation', 'appointment',
                'huddle', 'gathering', 'event', 'conference', 'briefing', 'check-in', 'standup',
                
                # Prepositions and conjunctions
                'at', 'for', 'with', 'by', 'to', 'in', 'on', 'of', 'from', 'about', 'between',
                'and', 'or', 'but', 'nor', 'yet', 'so', 'as', 'if', 'than', 'that', 'because',
                'a', 'an', 'the', 'this', 'these', 'those', 'next', 'last', 'previous', 'upcoming',
                
                # Time-related words not already in time_date_keywords
                'quick', 'brief', 'short', 'long', 'extended'
            ]
            prepositions = ['at', 'for', 'with', 'by', 'to', 'in', 'on', 'of', 'from', 'about',
                'and', 'or', 'but', 'nor', 'yet', 'so', 'as', 'if', 'than', 'that',
                'a', 'an', 'the', 'this', 'these', 'those']
            # Add these debugging logs for the original attendees
            self.logger.debug(f"Original attendees before filtering: {attendees}")
            self.logger.debug(f"Query words for filtering: {query_words}")
            self.logger.debug(f"Common words for filtering: {common_words}")
            self.logger.debug(f"Command words for filtering: {command_words}")
            self.logger.debug(f"Time/date keywords for filtering: {time_date_keywords}")

            filtered_attendees = []
            for name in attendees:
                # Convert to lowercase for comparison
                name_lower = name.lower()
                
                # Check common words first (including verbs, nouns, etc.)
                if name_lower in common_words:
                    self.logger.debug(f"Filtering out attendee '{name}' - matches common word")
                    continue
                    
                # Check if it's only standalone letters or very short
                if len(name_lower) <= 2:
                    self.logger.debug(f"Filtering out attendee '{name}' - too short")
                    continue
                
                # Skip if it's a query word, common word, or command word
                if name_lower in [q.lower() for q in query_words + command_words]:
                    self.logger.debug(f"Filtering out attendee '{name}' - matches query/command word")
                    continue
                
                # Add this check in your filtering logic
                if not self.looks_like_name(name):
                    self.logger.debug(f"Filtering out attendee '{name}' - doesn't look like a name")
                    continue

                # Skip if it's a time/date keyword
                if name_lower in time_date_keywords:
                    self.logger.debug(f"Filtering out attendee '{name}' - matches time/date keyword")
                    continue
                
                # Skip if it's only a number or contains mostly digits
                if name_lower.isdigit() or (sum(c.isdigit() for c in name_lower) / len(name_lower) > 0.5):
                    self.logger.debug(f"Filtering out attendee '{name}' - mostly numeric")
                    continue
                
                # Additional check for time/duration patterns
                skip = False
                for pattern in time_duration_regex:
                    if pattern.match(name_lower):
                        skip = True
                        self.logger.debug(f"Filtering out '{name}' - matches time/duration pattern")
                        break
                
                if skip:
                    continue
                
                # Skip if it appears in other entity types we've already extracted
                skip = False
                for entity_type in ['TIME', 'DATE', 'DURATION']:
                    for entity_value in entities.get(entity_type, []):
                        if name_lower in entity_value.lower():
                            skip = True
                            self.logger.debug(f"Filtering out attendee '{name}' - appears in {entity_type} entity")
                            break
                    if skip:
                        break
                
                if skip:
                    continue
                
                # If it passed all filters, add to filtered attendees
                self.logger.debug(f"Keeping attendee: '{name}' - passed all filters")
                filtered_attendees.append(name)

            # Remove duplicates while preserving order
            unique_attendees = []
            for attendee in filtered_attendees:
                if attendee not in unique_attendees:
                    unique_attendees.append(attendee)

            entities['ATTENDEE'] = unique_attendees
            self.logger.info(f"Final extracted attendees: {entities['ATTENDEE']}")
            
            # Apply conflict resolution as final step
            entities = self.filter_conflicting_entities(entities)
            
            # Log the complete extraction results
            self.logger.info("Entity extraction completed successfully")
            self.logger.debug(f"Complete extracted entities after conflict resolution: {entities}")
            
            return entities
        
        except Exception as e:
            self.logger.error(f"Error during entity extraction: {e}", exc_info=True)
            raise
                    
    def validate_attendees(self, attendees):
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
                # Add entire entity and individual words to the set
                extracted_tokens.add(entity.lower())
                extracted_tokens.update(word.lower() for word in entity.split())
                
                # Also add versions without common suffixes for time/duration
                clean_entity = re.sub(r'(am|pm|mins|min|hours|hour|hrs|hr)$', '', entity.lower()).strip()
                extracted_tokens.add(clean_entity)
        
        self.logger.debug(f"Tokens already extracted as other entities: {extracted_tokens}")
        
        # Additional regex patterns to identify time/duration strings
        duration_patterns = [
            r'^\d+\s*(?:mins|min|minutes|m)$',
            r'^\d+\s*(?:hours|hour|hrs|hr)$'
        ]
        
        time_patterns = [
            r'^\d+\s*(?:am|pm)$',
            r'^\d+:\d+\s*(?:am|pm)?$'
        ]
        
        common_prepositions = [
        'at', 'for', 'with', 'by', 'to', 'in', 'on', 'of', 'from', 'about',
        'and', 'or', 'but', 'nor', 'yet', 'so', 'as', 'if', 'than', 'that',
        'a', 'an', 'the', 'this', 'these', 'those'
        ]
        
        # Compile all patterns
        all_patterns = []
        for pattern in duration_patterns + time_patterns:
            all_patterns.append(re.compile(pattern, re.IGNORECASE))
        
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
            
            # Skip common prepositions and conjunctions
            if attendee.lower() in common_prepositions:
                self.logger.debug(f"Filtering out attendee '{attendee}' - common preposition/conjunction")
                continue
            # Additional check using compiled patterns
            matches_pattern = False
            for pattern in all_patterns:
                if pattern.match(attendee_lower):
                    matches_pattern = True
                    self.logger.debug(f"Filtering out attendee '{attendee}' - matches time/duration pattern")
                    break
            
            if matches_pattern:
                continue
                
            filtered_attendees.append(attendee)
        
        self.logger.info(f"Filtered attendees from {len(original_attendees)} to {len(filtered_attendees)}")
        entities['ATTENDEE'] = filtered_attendees
        
        return entities
        
    def looks_like_name(self, text):
        """
        Simple check if text could be a name
        """
        # Only filter out very short names or those with obvious non-name characteristics
        if len(text) <= 1:
            return False
            
        # Names don't typically contain digits
        if any(c.isdigit() for c in text):
            return False
            
        # Most names don't have special characters except hyphens and apostrophes
        if re.search(r'[^a-zA-Z\-\' ]', text):
            return False
            
        return True