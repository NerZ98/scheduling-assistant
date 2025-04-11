import logging
import random
import re
from collections import defaultdict
from datetime import datetime
import uuid
from typing import Dict, List, Tuple, Any, Optional

from database import ContactDatabase

class Chatbot:
    def __init__(self, extractor, config=None):
        """
        Initialize the chatbot with entity extractor and context storage
        
        Args:
            extractor: The entity extractor instance
            db_path (str): Path to the contacts database
        """
        self.extractor = extractor
        self.logger = logging.getLogger('Chatbot')
        
        # Initialize contact database
        self.contact_db = ContactDatabase(config, self.logger)
        
        # Dictionary to store conversation contexts
        # Format: {session_id: {entity_type: [values]}}
        self.contexts = {}
        
        # Required entity types for a complete conversation
        self.required_entities = ['DATE', 'TIME', 'DURATION', 'ATTENDEE']
        
        # Add greeting patterns and help patterns
        self.greeting_patterns = [
            r'\bhi\b',
            r'\bhello\b', 
            r'\bhey\b',
            r'\bgreetings\b',
            r'\bgood\s*(?:morning|afternoon|evening)\b',
            r'\bwhat\'?s?\s*up\b',
            r'\bhowdy\b'
        ]
        
        self.help_patterns = [
            r'\bhow\s+(?:do|can|should)\s+I\b',
            r'\bhelp\b',
            r'\bguide\b',
            r'\bhow\s+(?:does|to)\b',
            r'\bwhat\s+(?:can|should)\b',
            r'\binstruction',
            r'\bexplain\b'
        ]
        
        # Create responses for prompting missing information
        self.prompts = {
            'DATE': [
                "What day would you like to schedule this for?",
                "Could you tell me the date for this?",
                "I need to know when this should happen. Today, tomorrow, or a specific day?"
            ],
            'TIME': [
                "What time would work best?",
                "Could you specify a time for this?",
                "When during the day should this take place?"
            ],
            'DURATION': [
                "How long will this take?",
                "What's the expected duration?",
                "How many minutes or hours should I reserve for this?"
            ],
            'ATTENDEE': [
                "Who will be attending?",
                "Could you mention who needs to be included?",
                "Who should I add to this event?"
            ],
            'GREETING': [
                "Hello! I'm your scheduling assistant. How can I help you today?",
                "Hi there! I can help you schedule something. What would you like to plan?",
                "Welcome! I'm here to help with your scheduling needs. What can I do for you?"
            ],
            'CONFIRMATION': [
                "Great! I've got all the details I need.",
                "Perfect! I've collected all the necessary information.",
                "Thank you for providing all the details!"
            ],
            'SUMMARY': [
                "Here's what I have: ",
                "Let me summarize what we've planned: ",
                "Here's the summary of your event: "
            ],
            'CLARIFICATION': [
                "I'm not sure I understood that correctly. Could you please clarify?",
                "I didn't quite catch that. Can you rephrase?",
                "Sorry, I'm having trouble understanding. Could you explain differently?"
            ],
            'UNKNOWN': [
                "I'm not sure how to process that. Can you try phrasing it differently?",
                "I didn't understand that. Could you provide more details about what you're trying to schedule?",
                "I'm having trouble understanding. Let's try another approach. What are you trying to schedule?"
            ],
            'HELP': [
                "I'm your scheduling assistant. You can schedule meetings by telling me the date, time, duration, and attendees. For example, 'Schedule a meeting tomorrow at 3pm for 1 hour with John and Mary.' I'll ask for any missing information.",
                "To schedule something, just tell me when it should happen, for how long, and with whom. I'll guide you through the process by asking for any details you haven't provided.",
                "I can help you schedule events! Just mention the date (like 'tomorrow' or 'next Monday'), time (like '3pm'), duration (like '30 minutes'), and who's attending. I'll ask you for any information you haven't provided."
            ],
            'CONFIRMATION_REQUEST': [
                "Here's what I've got: {summary} Is this correct? (Yes/No)",
                "I've collected all the details: {summary} Does this look right? (Yes/No)",
                "Please confirm these meeting details: {summary} Is everything correct? (Yes/No)"
            ],
            'CHANGE_REQUEST': [
                "What would you like to change? You can update the date, time, duration, or attendees.",
                "Please let me know what detail needs to be updated. You can specify a new date, time, duration, or attendees.",
                "What detail would you like to modify? Just let me know the new information."
            ],
            'CONFIRMATION_YES': [
                "Great! I'll schedule this meeting now.",
                "Perfect! I'll go ahead and schedule this for you.",
                "Excellent! I'll set up this meeting immediately."
            ],
            'CONFIRMATION_NO': [
                "No problem. What would you like to change?",
                "I understand. What details would you like to update?",
                "Sure thing. Please tell me what needs to be corrected."
            ]
        }
    
    def reset_context(self, session_id: str) -> None:
        """
        Reset the conversation context for a session
        
        Args:
            session_id (str): The session identifier
        """
        self.contexts[session_id] = {
            'DATE': [],
            'TIME': [],
            'DURATION': [],
            'ATTENDEE': [],
            'ATTENDEE_EMAILS': {},
            'SUMMARY': None,
            'COMPLETE': False,
            'CONFIRMED': False,  # Tracks whether user has confirmed
            'AWAITING_CONFIRMATION': False  # Tracks if we're waiting for user to confirm
        }
        self.logger.info(f"Context reset for session {session_id}")
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current context for a session
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            Dict: Current context or empty dict if not found
        """
        return self.contexts.get(session_id, {})
    
    def update_context(self, session_id: str, entities: Dict[str, List[str]]) -> None:
        """
        Update the context with new entities
        
        Args:
            session_id (str): The session identifier
            entities (Dict[str, List[str]]): The entities to add
        """
        # Create context if it doesn't exist
        if session_id not in self.contexts:
            self.reset_context(session_id)
        
        # Update each entity type
        for entity_type, values in entities.items():
            if values:  # Only update if we have new values
                # For most entity types, replace old values with new ones
                # This handles updates to date, time, duration
                if entity_type in ['DATE', 'TIME', 'DURATION']:
                    self.contexts[session_id][entity_type] = values
                # For attendees, append new values
                else:
                    existing = set(self.contexts[session_id][entity_type])
                    new_values = existing.union(set(values))
                    self.contexts[session_id][entity_type] = list(new_values)
        
        # If we're updating entities, we need to reset confirmation status
        # because the details have changed
        if entities:
            self.contexts[session_id]['CONFIRMED'] = False
            self.contexts[session_id]['AWAITING_CONFIRMATION'] = False
        
        # Check if context is complete and update status
        self.check_context_completeness(session_id)
    
    def check_context_completeness(self, session_id: str) -> bool:
        """
        Check if all required entities are present
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            bool: True if context is complete, False otherwise
        """
        if session_id not in self.contexts:
            return False
        
        context = self.contexts[session_id]
        
        # Check each required entity type
        complete = True
        for entity in self.required_entities:
            if len(context.get(entity, [])) == 0:
                self.logger.debug(f"Missing required entity: {entity}")
                complete = False
                break
        
        # Update the complete status
        context['COMPLETE'] = complete
        
        # If complete, generate a summary
        if complete and not context.get('SUMMARY'):
            context['SUMMARY'] = self.generate_summary_with_emails(session_id)
            self.logger.info(f"Context complete for session {session_id}. Summary generated.")
        else:
            missing_entities = self.get_missing_entities(session_id)
            if missing_entities:
                self.logger.info(f"Context incomplete for session {session_id}. Missing: {missing_entities}")
            
        return complete

    def is_context_complete(self, session_id: str) -> bool:
        """
        Check if the context is complete and confirmed
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            bool: True if context is complete and confirmed, False otherwise
        """
        if session_id not in self.contexts:
            return False
        
        context = self.contexts[session_id]
        is_complete = context.get('COMPLETE', False)
        is_confirmed = context.get('CONFIRMED', False)
        
        # For external checks (like in app.py), we consider a context fully complete
        # only when all required fields are present AND the user has confirmed
        return is_complete and is_confirmed
    
    def get_missing_entities(self, session_id: str) -> List[str]:
        """
        Get list of missing required entities
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            List[str]: List of missing entity types
        """
        if session_id not in self.contexts:
            return self.required_entities
        
        missing = []
        context = self.contexts[session_id]
        
        for entity in self.required_entities:
            if not context.get(entity, []):
                missing.append(entity)
        
        return missing
    
    def generate_prompt(self, session_id: str) -> str:
        """
        Generate a prompt for missing information
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            str: Prompt message
        """
        missing = self.get_missing_entities(session_id)
        
        if not missing:
            return random.choice(self.prompts['CONFIRMATION'])
        
        # Prioritize asking for one piece of missing information at a time
        entity_to_ask = missing[0]
        return random.choice(self.prompts[entity_to_ask])
    
    def check_special_intents(self, message: str) -> str:
        """
        Check for special intents like greetings or help requests
        
        Args:
            message (str): The user message
            
        Returns:
            str: Response message if special intent found, empty string otherwise
        """
        # Check for greeting patterns
        for pattern in self.greeting_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                self.logger.debug(f"Greeting pattern detected: {pattern}")
                return random.choice(self.prompts['GREETING'])
        
        # Check for help patterns
        for pattern in self.help_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                self.logger.debug(f"Help pattern detected: {pattern}")
                return random.choice(self.prompts['HELP'])
        
        # No special intent found
        return ""
    
    def parse_multiple_selections(self, message: str, options: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse a message for multiple selection numbers
        
        Args:
            message (str): The user message
            options (List[Dict]): The available options
            
        Returns:
            List[Dict]: Selected contacts or empty list if invalid
        """
        # Common patterns for multiple selections
        selections = []
        
        # Check for keywords indicating multiple selection
        if any(word in message.lower() for word in ['both', 'all', 'everyone']):
            # User wants all options
            return options
        
        # Check for "and" or comma-separated numbers
        if 'and' in message or ',' in message:
            # Replace 'and' with comma for consistent parsing
            selection_text = message.replace(' and ', ',').replace('&', ',')
            # Split by comma and strip whitespace
            selection_parts = [part.strip() for part in selection_text.split(',')]
            
            # Try to parse each part as a number
            for part in selection_parts:
                try:
                    num = int(part)
                    if 1 <= num <= len(options):
                        selections.append(options[num-1])
                except ValueError:
                    continue
        else:
            # Try single number
            try:
                num = int(message.strip())
                if 1 <= num <= len(options):
                    selections.append(options[num-1])
            except ValueError:
                pass
        
        return selections
    
    def lookup_emails_for_attendees(self, session_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Look up emails for attendees in the context
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            Dict[str, List[Dict]]: Dictionary of attendee names mapped to contact records
        """
        if session_id not in self.contexts:
            return {}
        
        context = self.contexts[session_id]
        attendees = context.get('ATTENDEE', [])
        
        if not attendees:
            return {}
        
        # Look up each attendee in the database
        attendee_records = {}
        for attendee in attendees:
            # Skip attendees that already have emails in their name
            if '(' in attendee and '@' in attendee and ')' in attendee:
                continue
                
            # Search for contacts matching this name
            contacts = self.contact_db.find_contacts_by_name(attendee)
            if contacts:
                attendee_records[attendee] = contacts
                self.logger.debug(f"Found {len(contacts)} contacts for '{attendee}'")
            else:
                self.logger.debug(f"No contacts found for '{attendee}'")
        
        return attendee_records
    
    def check_ambiguous_attendees(self, session_id: str) -> Optional[Tuple[str, List[Dict[str, Any]]]]:
        """
        Check if there are any attendees with ambiguous (multiple) records
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            Optional[Tuple[str, List[Dict]]]: First ambiguous attendee and their records, or None
        """
        if session_id not in self.contexts:
            return None
        
        # Get attendees
        attendees = self.contexts[session_id].get('ATTENDEE', [])
        
        # Get already selected emails
        selected_emails = self.contexts[session_id].get('ATTENDEE_EMAILS', {})
        
        # Check each attendee that doesn't already have an email selection
        for attendee in attendees:
            # Skip attendees that already have emails in their name
            if '(' in attendee and '@' in attendee and ')' in attendee:
                continue
                
            if attendee in selected_emails:
                # Already has an email selection
                continue
                
            # Search for contacts matching this name
            contacts = self.contact_db.find_contacts_by_name(attendee)
            
            # If multiple contacts found, return this attendee and the records
            if len(contacts) > 1:
                self.logger.info(f"Found {len(contacts)} contacts for attendee '{attendee}'")
                return attendee, contacts
        
        # No ambiguous attendees found
        return None
    
    def handle_email_selection(self, session_id: str, attendee: str, email: str) -> None:
        """
        Handle selection of email when multiple contacts share the same name
        
        Args:
            session_id (str): The session identifier
            attendee (str): The attendee name
            email (str): The selected email
        """
        if session_id not in self.contexts:
            return
        
        # Store the email selection in the context
        if 'ATTENDEE_EMAILS' not in self.contexts[session_id]:
            self.contexts[session_id]['ATTENDEE_EMAILS'] = {}
        
        self.contexts[session_id]['ATTENDEE_EMAILS'][attendee] = email
        self.logger.info(f"Email '{email}' selected for attendee '{attendee}'")
    
    def format_contact_options(self, contacts: List[Dict[str, Any]]) -> str:
        """
        Format contact options for selection
        
        Args:
            contacts (List[Dict]): List of contact records
            
        Returns:
            str: Formatted options text
        """
        options = []
        for i, contact in enumerate(contacts, 1):
            name = f"{contact['first_name']} {contact['last_name']}"
            email = contact['email']
            options.append(f"{i}. {name} ({email})")
        
        return "\n".join(options)
    
    def generate_summary_with_emails(self, session_id: str) -> str:
        """
        Generate a summary of the scheduling information including emails
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            str: Summary message with emails
        """
        context = self.contexts[session_id]
        date = context.get('DATE', ['(no date specified)'])[0]
        time = context.get('TIME', ['(no time specified)'])[0]
        duration = context.get('DURATION', ['(no duration specified)'])[0]
        
        # Get attendees with emails
        attendees = context.get('ATTENDEE', [])
        attendee_emails = context.get('ATTENDEE_EMAILS', {})
        
        # Format attendees with emails
        formatted_attendees = []
        missing_emails = []
        
        for attendee in attendees:
            # If attendee already has an email in their name
            if '(' in attendee and '@' in attendee and ')' in attendee:
                formatted_attendees.append(attendee)
                continue
                
            if attendee in attendee_emails:
                # Use the email that was explicitly selected
                formatted_attendees.append(f"{attendee} ({attendee_emails[attendee]})")
            else:
                # Try to look up in the database
                contacts = self.contact_db.find_contacts_by_name(attendee)
                if len(contacts) == 1:
                    # Single match - no ambiguity
                    email = contacts[0]['email']
                    formatted_attendees.append(f"{attendee} ({email})")
                    # Store for future reference
                    attendee_emails[attendee] = email
                elif len(contacts) > 1:
                    # Multiple matches but no selection was made
                    # This shouldn't happen if we properly prompt for selection, but just in case
                    missing_emails.append(attendee)
                    formatted_attendees.append(f"{attendee} (email selection needed)")
                else:
                    # No match
                    missing_emails.append(attendee)
                    formatted_attendees.append(f"{attendee} (no email found)")
        
        # Store updated emails
        self.contexts[session_id]['ATTENDEE_EMAILS'] = attendee_emails
        
        # Format summary - ensure no unwanted formatting characters like **
        attendees_text = ", ".join(formatted_attendees)
        title = "Meeting"
        
        # Clean the summary of any potential markdown or formatting characters
        summary = f"{title} scheduled for {date} at {time}, lasting {duration}, with {attendees_text}."
        
        # If there are missing emails, add a note
        if missing_emails:
            if len(missing_emails) == 1:
                summary += f" Note: No email was found for {missing_emails[0]}."
            else:
                missing_names = ", ".join(missing_emails)
                summary += f" Note: No emails were found for these attendees: {missing_names}."
        
        return summary

    def handle_confirmation_response(self, message: str, session_id: str) -> str:
        """
        Handle user's response to a confirmation request
        
        Args:
            message (str): The user message
            session_id (str): The session identifier
            
        Returns:
            str: Response message
        """
        # Normalize the message text for easier matching
        normalized_message = message.lower().strip()
        
        # Check for positive responses
        positive_responses = ['yes', 'yeah', 'yep', 'correct', 'right', 'looks good', 'sure', 'confirm', 'ok', 'okay']
        negative_responses = ['no', 'nope', 'not correct', 'wrong', 'change', 'modify', 'update', 'incorrect', 'fix']
        
        if any(pos in normalized_message for pos in positive_responses):
            # User confirmed the meeting details
            self.contexts[session_id]['CONFIRMED'] = True
            self.contexts[session_id]['AWAITING_CONFIRMATION'] = False
            return random.choice(self.prompts['CONFIRMATION_YES'])
        
        elif any(neg in normalized_message for neg in negative_responses):
            # User wants to change something
            self.contexts[session_id]['AWAITING_CONFIRMATION'] = False
            return random.choice(self.prompts['CHANGE_REQUEST'])
        
        else:
            # Unclear response, ask again
            return "I didn't understand. Please answer 'yes' to confirm or 'no' to make changes."
    
    def process_message(self, message: str, session_id: str) -> Tuple[str, Dict[str, List[str]]]:
        """
        Process a user message and update context
        
        Args:
            message (str): The user message
            session_id (str): The session identifier
            
        Returns:
            Tuple[str, Dict[str, List[str]]]: Bot response and extracted entities
        """
        try:
            # Log context state at the beginning
            self.log_context_state(session_id, "Starting process_message")
            
            # Initialize context if it doesn't exist
            if session_id not in self.contexts:
                self.reset_context(session_id)
            
            # If we're awaiting confirmation, handle the confirmation response
            if self.contexts[session_id].get('AWAITING_CONFIRMATION', False):
                response = self.handle_confirmation_response(message, session_id)
                
                # Log context state before returning
                self.log_context_state(session_id, "Finished process_message - confirmation response")
                return response, {}
                
            # Check if this is an email selection message
            if session_id in self.contexts and 'PENDING_EMAIL_SELECTION' in self.contexts[session_id]:
                # Store the original entities before processing the selection
                original_entities = {}
                
                # Create a copy of all existing entities to preserve them
                for entity_type in self.required_entities:
                    if entity_type in self.contexts[session_id] and self.contexts[session_id][entity_type]:
                        original_entities[entity_type] = self.contexts[session_id][entity_type].copy()
                
                attendee = self.contexts[session_id]['PENDING_EMAIL_SELECTION']['attendee']
                options = self.contexts[session_id]['PENDING_EMAIL_SELECTION']['options']
                
                # Try to parse the selection (including multiple selections)
                selected_contacts = self.parse_multiple_selections(message, options)
                
                if selected_contacts:
                    # Handle valid selections
                    selected_names = []
                    selected_emails = []
                    
                    # Process each selected contact
                    for contact in selected_contacts:
                        email = contact['email']
                        name = f"{contact['first_name']} {contact['last_name']}"
                        selected_names.append(name)
                        selected_emails.append(email)
                        
                        # Update attendee list to include the specific contact
                        specific_attendee = f"{name} ({email})"
                        
                        # Add to context if not already present
                        if specific_attendee not in self.contexts[session_id]['ATTENDEE']:
                            self.contexts[session_id]['ATTENDEE'].append(specific_attendee)
                    
                    # Remove the generic attendee name
                    if attendee in self.contexts[session_id]['ATTENDEE']:
                        self.contexts[session_id]['ATTENDEE'].remove(attendee)
                    
                    # Store emails in the context
                    for idx, contact in enumerate(selected_contacts):
                        attendee_with_email = f"{selected_names[idx]} ({selected_emails[idx]})"
                        self.handle_email_selection(session_id, attendee_with_email, selected_emails[idx])
                    
                    # Clear the pending selection
                    del self.contexts[session_id]['PENDING_EMAIL_SELECTION']
                    
                    # Restore original entities that might have been lost during selection
                    for entity_type, values in original_entities.items():
                        if entity_type != 'ATTENDEE':  # Don't overwrite attendees
                            if entity_type not in self.contexts[session_id] or not self.contexts[session_id][entity_type]:
                                self.contexts[session_id][entity_type] = values
                    
                    # Format selections for response
                    selection_text = ""
                    if len(selected_contacts) == 1:
                        selection_text = f"{selected_names[0]} ({selected_emails[0]})"
                    else:
                        names_with_emails = [f"{name} ({email})" for name, email in zip(selected_names, selected_emails)]
                        selection_text = ", ".join(names_with_emails)
                    
                    # After successfully handling a selection, check if there are more ambiguous attendees
                    if 'ALL_AMBIGUOUS_ATTENDEES' in self.contexts[session_id]:
                        current_index = self.contexts[session_id].get('CURRENT_AMBIGUOUS_INDEX', 0)
                        all_ambiguous = self.contexts[session_id]['ALL_AMBIGUOUS_ATTENDEES']
                        
                        # Move to next ambiguous attendee if there are more
                        next_index = current_index + 1
                        if next_index < len(all_ambiguous):
                            self.contexts[session_id]['CURRENT_AMBIGUOUS_INDEX'] = next_index
                            next_attendee, next_records = all_ambiguous[next_index]
                            options_text = self.format_contact_options(next_records)
                            
                            # Set the pending selection for the next attendee
                            self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                                'attendee': next_attendee,
                                'options': next_records
                            }
                            
                            # Log context state before returning
                            self.log_context_state(session_id, "Processing next ambiguous attendee")
                            return f"Selected {selection_text}. Multiple contacts found for '{next_attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", {}
                        else:
                            # No more ambiguous attendees, clean up
                            del self.contexts[session_id]['ALL_AMBIGUOUS_ATTENDEES']
                            del self.contexts[session_id]['CURRENT_AMBIGUOUS_INDEX']
                    
                    # Check if there are more ambiguous attendees that haven't been handled yet
                    next_ambiguous = self.check_ambiguous_attendees(session_id)
                    if next_ambiguous:
                        next_attendee, next_records = next_ambiguous
                        options_text = self.format_contact_options(next_records)
                        
                        # Set the pending selection for the next attendee
                        self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                            'attendee': next_attendee,
                            'options': next_records
                        }
                        
                        # Log context state before returning
                        self.log_context_state(session_id, "Found more ambiguous attendees")
                        return f"Selected {selection_text}. Multiple contacts found for '{next_attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", {}
                    
                    # Check context completeness AFTER selection to ensure it's fully evaluated
                    is_complete = self.check_context_completeness(session_id)
                    
                    # If context is complete, show confirmation step
                    if is_complete and not self.contexts[session_id].get('AWAITING_CONFIRMATION', False):
                        self.contexts[session_id]['AWAITING_CONFIRMATION'] = True
                        summary = self.generate_summary_with_emails(session_id)
                        confirmation_request = random.choice(self.prompts['CONFIRMATION_REQUEST']).format(summary=summary)
                        
                        # Log context state before returning
                        self.log_context_state(session_id, "Confirming after selection")
                        return f"Selected {selection_text}. {confirmation_request}", {}
                    # Otherwise, prompt for missing information
                    # Log context state before returning
                    self.log_context_state(session_id, "Prompting for missing info after selection")
                    return f"Selected {selection_text}. " + self.generate_prompt(session_id), {}
                
                # Invalid selection
                options_text = self.format_contact_options(options)
                
                # Log context state before returning
                self.log_context_state(session_id, "Invalid selection")
                return f"Invalid selection. Please select one or more numbers from the list (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", {}
            
            # Extract entities from the message first
            entities = self.extractor.extract_entities(message)
            self.logger.info(f"Extracted entities: {entities}")
            
            # Check for special intents (greetings, help)
            special_response = self.check_special_intents(message)
            if special_response:
                # Return the special response with empty entities
                # Log context state before returning
                self.log_context_state(session_id, "Special intent detected")
                return special_response, {}
            
            # Process attendees before updating context
            if 'ATTENDEE' in entities and entities['ATTENDEE']:
                self.logger.info(f"Processing attendees: {entities['ATTENDEE']}")
                
                # Validate attendees against contacts database
                valid_attendees, invalid_attendees = self.validate_attendees(entities['ATTENDEE'])
                
                # If there are invalid attendees, respond with detailed error
                if invalid_attendees:
                    if len(invalid_attendees) == 1:
                        # Show a list of similar names if possible
                        similar_names = []
                        all_contacts = self.contact_db.get_all_contacts()
                        for contact in all_contacts[:10]:  # Limit to first 10 contacts
                            similar_names.append(f"{contact['first_name']} {contact['last_name']}")
                        
                        suggestions = ", ".join(similar_names[:5])  # Show up to 5 suggestions
                        
                        # Log context state before returning
                        self.log_context_state(session_id, "Invalid attendee - not found")
                        return f"'{invalid_attendees[0]}' is not in the organization's contact list. Please choose from contacts like: {suggestions}", {}
                    else:
                        invalid_list = ", ".join([f"'{a}'" for a in invalid_attendees])
                        
                        # Log context state before returning
                        self.log_context_state(session_id, "Multiple invalid attendees")
                        return f"The following people are not in the organization's contact list: {invalid_list}. Please choose attendees from the organization.", {}
                
                # Process valid attendees
                found_attendees = []
                ambiguous_attendees = []
                
                for attendee in valid_attendees:
                    # Skip attendees that already have emails in their name
                    if '(' in attendee and '@' in attendee and ')' in attendee:
                        found_attendees.append(attendee)
                        continue
                    
                    # Search for contacts matching this name
                    contacts = self.contact_db.find_contacts_by_name(attendee)
                    
                    if len(contacts) == 1:
                        # Single match - add directly
                        contact = contacts[0]
                        email = contact['email']
                        name = f"{contact['first_name']} {contact['last_name']}"
                        specific_attendee = f"{name} ({email})"
                        
                        found_attendees.append(attendee)
                        
                        # Add to context (create if needed)
                        if 'ATTENDEE' not in self.contexts[session_id]:
                            self.contexts[session_id]['ATTENDEE'] = []
                        
                        if specific_attendee not in self.contexts[session_id]['ATTENDEE']:
                            self.contexts[session_id]['ATTENDEE'].append(specific_attendee)
                            self.logger.info(f"Added single match attendee: {specific_attendee}")
                            
                        # Store the email
                        self.handle_email_selection(session_id, specific_attendee, email)
                    elif len(contacts) > 1:
                        # Multiple matches - need user selection
                        ambiguous_attendees.append((attendee, contacts))
                        found_attendees.append(attendee)
                
                # Store the original entities before handling ambiguous attendees
                # This is to preserve date, time, and duration information
                original_entities = {}
                for entity_type, values in entities.items():
                    if entity_type != 'ATTENDEE' and values:  # Don't overwrite attendees
                        original_entities[entity_type] = values.copy()
                
                # Store all ambiguous attendees for sequential processing
                if ambiguous_attendees:
                    self.contexts[session_id]['ALL_AMBIGUOUS_ATTENDEES'] = ambiguous_attendees
                    self.contexts[session_id]['CURRENT_AMBIGUOUS_INDEX'] = 0
                    
                    # Handle the first ambiguous attendee
                    attendee, records = ambiguous_attendees[0]
                    options_text = self.format_contact_options(records)
                    
                    # Store original entities in the context
                    for entity_type, values in original_entities.items():
                        if entity_type not in self.contexts[session_id] or not self.contexts[session_id][entity_type]:
                            self.contexts[session_id][entity_type] = values
                    
                    # Set pending email selection in context
                    self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                        'attendee': attendee,
                        'options': records,
                        'original_entities': original_entities  # Store original entities
                    }
                    
                    # Log context state before returning
                    self.log_context_state(session_id, "Multiple contacts for attendee")
                    return f"Multiple contacts found for '{attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", entities
                
                # Update only non-attendee entities, since we've already handled attendees
                other_entities = {k: v for k, v in entities.items() if k != 'ATTENDEE'}
                self.update_context(session_id, other_entities)
            else:
                # No attendees to process, update context with all entities
                self.update_context(session_id, entities)
            
            # Check if there are ambiguous attendees that haven't been handled yet
            if not self.contexts[session_id].get('PENDING_EMAIL_SELECTION'):
                # Get all ambiguous attendees
                all_ambiguous_attendees = self.check_all_ambiguous_attendees(session_id)
                
                if all_ambiguous_attendees:
                    # Store all ambiguous attendees in context for sequential processing
                    self.contexts[session_id]['ALL_AMBIGUOUS_ATTENDEES'] = all_ambiguous_attendees
                    self.contexts[session_id]['CURRENT_AMBIGUOUS_INDEX'] = 0
                    
                    # Start with the first ambiguous attendee
                    attendee, records = all_ambiguous_attendees[0]
                    options_text = self.format_contact_options(records)
                    
                    # Set pending email selection in context
                    self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                        'attendee': attendee,
                        'options': records
                    }
                    
                    # Log context state before returning
                    self.log_context_state(session_id, "Found ambiguous attendee after update")
                    return f"Multiple contacts found for '{attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", entities
            
            # Check if the context is complete
            is_complete = self.check_context_completeness(session_id)
            
            if is_complete:
                # If we haven't asked for confirmation yet and the user hasn't confirmed
                if not self.contexts[session_id].get('AWAITING_CONFIRMATION', False) and not self.contexts[session_id].get('CONFIRMED', False):
                    # Set awaiting confirmation flag
                    self.contexts[session_id]['AWAITING_CONFIRMATION'] = True
                    
                    # Generate a summary and ask for confirmation
                    summary = self.generate_summary_with_emails(session_id)
                    confirmation_request = random.choice(self.prompts['CONFIRMATION_REQUEST']).format(summary=summary)
                    
                    # Log context state before returning
                    self.log_context_state(session_id, "Asking for confirmation")
                    return confirmation_request, entities
                
                # If user has confirmed, generate a confirmed summary response
                if self.contexts[session_id].get('CONFIRMED', False):
                    summary = self.generate_summary_with_emails(session_id)
                    response = f"{random.choice(self.prompts['CONFIRMATION_YES'])} {random.choice(self.prompts['SUMMARY'])} {summary}"
                    
                    # Log context state before returning
                    self.log_context_state(session_id, "Confirmed scheduling")
                    return response, entities
            
            # Generate a prompt for missing information
            response = self.generate_prompt(session_id)
            
            # Log context state before returning
            self.log_context_state(session_id, "Prompting for missing information")
            return response, entities
        
        except Exception as e:
            self.logger.error(f"Error processing message: {e}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
            return random.choice(self.prompts['UNKNOWN']), {}
 
                                
    def generate_summary_with_teams_link(self, session_id: str, teams_link: str = None) -> str:
        """
        Generate a summary of the scheduling information including emails and Teams link
        
        Args:
            session_id (str): The session identifier
            teams_link (str, optional): Microsoft Teams meeting link
            
        Returns:
            str: Summary message with emails and Teams link
        """
        # First, get the regular summary
        summary = self.generate_summary_with_emails(session_id)
        
        # If a Teams link is provided, append it to the summary
        if teams_link:
            summary += f"\n\nYou can join the meeting using this Microsoft Teams link: {teams_link}"
        
        return summary

    def update_context_with_teams_link(self, session_id: str, teams_link: str) -> None:
        """
        Update the context with a Microsoft Teams meeting link
        
        Args:
            session_id (str): The session identifier
            teams_link (str): Microsoft Teams meeting link
        """
        if session_id not in self.contexts:
            return
        
        # Add Teams link to context
        self.contexts[session_id]['TEAMS_LINK'] = teams_link
        
        # Update summary if it exists
        if self.contexts[session_id].get('SUMMARY'):
            self.contexts[session_id]['SUMMARY'] = self.generate_summary_with_teams_link(
                session_id, teams_link
            )
        
        self.logger.info(f"Updated context with Teams link for session {session_id}")

    def prepare_meeting_data(self, session_id: str) -> dict:
        """
        Prepare meeting data for Microsoft Graph API
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            dict: Meeting data formatted for Microsoft Graph API
        """
        if session_id not in self.contexts:
            return {}
        
        context = self.contexts[session_id]
        
        # Get basic meeting details
        date = context.get('DATE', [''])[0]
        time = context.get('TIME', [''])[0]
        duration = context.get('DURATION', [''])[0]
        attendees = context.get('ATTENDEE', [])
        
        # Extract email addresses from attendees
        email_addresses = []
        for attendee in attendees:
            # Try to extract email from format "Name (email@example.com)"
            import re
            email_match = re.search(r'\(([^)]+@[^)]+)\)', attendee)
            
            if email_match:
                email_addresses.append(email_match.group(1))
        
        # Create meeting data
        meeting_data = {
            'subject': f"Meeting on {date} at {time}",
            'body': f"Meeting scheduled via Scheduling Assistant\n\nDate: {date}\nTime: {time}\nDuration: {duration}\nAttendees: {', '.join(attendees)}",
            'attendees': email_addresses
        }
        
        return meeting_data
    
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
    
    def log_context_state(self, session_id: str, prefix: str = "Context state") -> None:
        """
        Log the current state of the context for debugging
        
        Args:
            session_id (str): The session identifier
            prefix (str): Prefix for the log message
        """
        if session_id not in self.contexts:
            self.logger.debug(f"{prefix}: No context for session {session_id}")
            return
            
        context = self.contexts[session_id]
        
        # Log attendees with their status
        attendees = context.get('ATTENDEE', [])
        attendee_emails = context.get('ATTENDEE_EMAILS', {})
        
        self.logger.debug(f"{prefix}: Session {session_id}")
        self.logger.debug(f"  DATE: {context.get('DATE', [])}")
        self.logger.debug(f"  TIME: {context.get('TIME', [])}")
        self.logger.debug(f"  DURATION: {context.get('DURATION', [])}")
        
        # More detailed logging for attendees
        self.logger.debug(f"  ATTENDEE count: {len(attendees)}")
        for i, attendee in enumerate(attendees):
            has_email = '(' in attendee and '@' in attendee and ')' in attendee
            has_selection = attendee in attendee_emails
            email = attendee_emails.get(attendee, None) if has_selection else None
            
            status = "has embedded email" if has_email else (
                f"has selected email: {email}" if has_selection else "needs email resolution"
            )
            
            self.logger.debug(f"    [{i}] {attendee} - {status}")
        
        # Log ambiguity handling state
        pending = context.get('PENDING_EMAIL_SELECTION', None)
        if pending:
            self.logger.debug(f"  Waiting for email selection for: {pending.get('attendee')}")
        
        all_ambiguous = context.get('ALL_AMBIGUOUS_ATTENDEES', [])
        if all_ambiguous:
            current_idx = context.get('CURRENT_AMBIGUOUS_INDEX', 0)
            self.logger.debug(f"  Processing ambiguous attendees: {len(all_ambiguous)} total, currently at index {current_idx}")
        
        is_complete = context.get('COMPLETE', False)
        is_confirmed = context.get('CONFIRMED', False)
        awaiting_confirmation = context.get('AWAITING_CONFIRMATION', False)
        
        self.logger.debug(f"  State: complete={is_complete}, confirmed={is_confirmed}, awaiting_confirmation={awaiting_confirmation}")
        
    def check_all_ambiguous_attendees(self, session_id: str) -> List[Tuple[str, List[Dict[str, Any]]]]:
        """
        Check if there are any attendees with ambiguous (multiple) records
        and return all of them at once
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            List[Tuple[str, List[Dict]]]: List of tuples containing (attendee_name, records_list)
        """
        if session_id not in self.contexts:
            return []
        
        # Get attendees
        attendees = self.contexts[session_id].get('ATTENDEE', [])
        
        # Get already selected emails
        selected_emails = self.contexts[session_id].get('ATTENDEE_EMAILS', {})
        
        # List to store all ambiguous attendees
        all_ambiguous = []
        
        # Process each attendee by their full name
        for attendee in attendees:
            # Skip attendees that already have emails in their name
            if '(' in attendee and '@' in attendee and ')' in attendee:
                continue
                
            if attendee in selected_emails:
                # Already has an email selection
                continue
            
            # Improved handling for searching contacts by name
            contacts = []
            
            # Check if this is a full name (first and last)
            name_parts = attendee.split()
            if len(name_parts) >= 2:
                # This is a full name, search for exact match first
                contacts = self.contact_db.find_contacts_by_name(attendee)
                
                # If no exact match, try searching just by last name as fallback
                if not contacts:
                    last_name = name_parts[-1]
                    contacts = self.contact_db.find_contacts_by_name(last_name)
            else:
                # Single name component - search as is
                contacts = self.contact_db.find_contacts_by_name(attendee)
                
            # If multiple contacts found, add this attendee and the records to our list
            if len(contacts) > 1:
                self.logger.info(f"Found {len(contacts)} contacts for attendee '{attendee}'")
                all_ambiguous.append((attendee, contacts))
        
        # Return list of all ambiguous attendees
        return all_ambiguous