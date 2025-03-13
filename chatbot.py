import logging
import random
import re
from collections import defaultdict
from datetime import datetime
import uuid
from typing import Dict, List, Tuple, Any, Optional

from database import ContactDatabase

class Chatbot:
    def __init__(self, extractor, db_path='contacts.db'):
        """
        Initialize the chatbot with entity extractor and context storage
        
        Args:
            extractor: The entity extractor instance
            db_path (str): Path to the contacts database
        """
        self.extractor = extractor
        self.logger = logging.getLogger('Chatbot')
        
        # Initialize contact database
        self.contact_db = ContactDatabase(db_path, self.logger)
        
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
            'COMPLETE': False
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
        Check if the context is complete
        
        Args:
            session_id (str): The session identifier
            
        Returns:
            bool: True if context is complete, False otherwise
        """
        if session_id not in self.contexts:
            return False
        
        return self.contexts[session_id].get('COMPLETE', False)
    
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
        
        # Format summary
        attendees_text = ", ".join(formatted_attendees)
        title = "Meeting"
        
        summary = f"{title} scheduled for {date} at {time}, lasting {duration}, with {attendees_text}."
        
        # If there are missing emails, add a note
        if missing_emails:
            if len(missing_emails) == 1:
                summary += f" Note: No email was found for {missing_emails[0]}."
            else:
                missing_names = ", ".join(missing_emails)
                summary += f" Note: No emails were found for these attendees: {missing_names}."
        
        return summary
    
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
            # Initialize context if it doesn't exist
            if session_id not in self.contexts:
                self.reset_context(session_id)
                
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
                    
                    # Check if there are more ambiguous attendees
                    next_ambiguous = self.check_ambiguous_attendees(session_id)
                    if next_ambiguous:
                        next_attendee, next_records = next_ambiguous
                        options_text = self.format_contact_options(next_records)
                        
                        # Set the pending selection for the next attendee
                        self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                            'attendee': next_attendee,
                            'options': next_records
                        }
                        
                        return f"Selected {selection_text}. Multiple contacts found for '{next_attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", {}
                    
                    # Check context completeness AFTER selection to ensure it's fully evaluated
                    is_complete = self.check_context_completeness(session_id)
                    
                    # If context is complete, generate summary
                    if is_complete:
                        summary = self.generate_summary_with_emails(session_id)
                        response = f"Selected {selection_text}. {random.choice(self.prompts['CONFIRMATION'])} {random.choice(self.prompts['SUMMARY'])} {summary}"
                        return response, {}
                    
                    # Otherwise, prompt for missing information
                    return f"Selected {selection_text}. " + self.generate_prompt(session_id), {}
                
                # Invalid selection
                options_text = self.format_contact_options(options)
                return f"Invalid selection. Please select one or more numbers from the list (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", {}
            
            # Extract entities from the message first
            entities = self.extractor.extract_entities(message)
            self.logger.info(f"Extracted entities: {entities}")
            
            # Check for special intents (greetings, help)
            special_response = self.check_special_intents(message)
            if special_response:
                # Return the special response with empty entities
                return special_response, {}
            
            # Process attendees before updating context
            if 'ATTENDEE' in entities and entities['ATTENDEE']:
                not_found_attendees = []
                found_attendees = []
                ambiguous_attendees = []
                
                self.logger.info(f"Processing attendees: {entities['ATTENDEE']}")
                
                for attendee in entities['ATTENDEE']:
                    # Skip attendees that already have emails in their name
                    if '(' in attendee and '@' in attendee and ')' in attendee:
                        found_attendees.append(attendee)
                        continue
                    
                    # Search for contacts matching this name
                    self.logger.info(f"Looking up contact for name: '{attendee}'")
                    contacts = self.contact_db.find_contacts_by_name(attendee)
                    
                    self.logger.info(f"Found {len(contacts)} contacts for '{attendee}'")
                    
                    if len(contacts) > 0:
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
                        else:
                            # Multiple matches - need user selection
                            ambiguous_attendees.append((attendee, contacts))
                            found_attendees.append(attendee)
                    else:
                        not_found_attendees.append(attendee)
                
                # If there are attendees not found in the database, respond with error
                if not_found_attendees:
                    attendee_list = ", ".join([f"'{a}'" for a in not_found_attendees])
                    if len(not_found_attendees) == 1:
                        return f"{attendee_list} is not in the organization's contact list. Please choose someone from the organization.", {}
                    else:
                        return f"The following people are not in the organization's contact list: {attendee_list}. Please choose attendees from the organization.", {}
                
                # Store the original entities before handling ambiguous attendees
                # This is to preserve date, time, and duration information
                for entity_type, values in entities.items():
                    if entity_type != 'ATTENDEE' and values:  # Don't overwrite attendees
                        if entity_type not in self.contexts[session_id] or not self.contexts[session_id][entity_type]:
                            self.contexts[session_id][entity_type] = values.copy()
                
                # If there are ambiguous attendees, handle the first one
                if ambiguous_attendees:
                    attendee, records = ambiguous_attendees[0]
                    options_text = self.format_contact_options(records)
                    
                    # Set pending email selection in context
                    self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                        'attendee': attendee,
                        'options': records
                    }
                    
                    return f"Multiple contacts found for '{attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", entities
                
                # Update only non-attendee entities, since we've already handled attendees
                other_entities = {k: v for k, v in entities.items() if k != 'ATTENDEE'}
                self.update_context(session_id, other_entities)
            else:
                # No attendees to process, update context with all entities
                self.update_context(session_id, entities)
            
            # Check if there are ambiguous attendees that haven't been handled yet
            ambiguous_attendee = self.check_ambiguous_attendees(session_id)
            if ambiguous_attendee:
                attendee, records = ambiguous_attendee
                options_text = self.format_contact_options(records)
                
                # Set pending email selection in context
                self.contexts[session_id]['PENDING_EMAIL_SELECTION'] = {
                    'attendee': attendee,
                    'options': records
                }
                
                return f"Multiple contacts found for '{attendee}'. Please select one or more by number (e.g., '1', '2', '1 and 2', or 'all'):\n{options_text}", entities
            
            # Check if the context is complete
            is_complete = self.check_context_completeness(session_id)
            
            if is_complete:
                # Generate a summary response with emails
                summary = self.generate_summary_with_emails(session_id)
                response = f"{random.choice(self.prompts['CONFIRMATION'])} {random.choice(self.prompts['SUMMARY'])} {summary}"
            else:
                # Generate a prompt for missing information
                response = self.generate_prompt(session_id)
            
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