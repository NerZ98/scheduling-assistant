from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import argparse
from datetime import datetime
import uuid
import logging
import secrets
from flask_session import Session

# Create Flask app first
app = Flask(__name__)

# Generate a strong secret key
app.secret_key = secrets.token_hex(16)

# Configure server-side sessions - CRITICAL FOR MICROSOFT AUTH
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.getcwd(), 'flask_session')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'scheduling_assistant_'

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize Flask-Session BEFORE loading other configs
Session(app)

# Now load the rest of the configurations and imports
from config import get_config
from extractor import AdvancedEntityExtractor
from chatbot import Chatbot
from database import ContactDatabase
from graph_client import GraphClient
from ms_database import MeetingDatabase
import json

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Scheduling Assistant Chatbot")
    parser.add_argument('--seed-db', action='store_true', help="Seed the database with sample data")
    return parser.parse_args()

def initialize_database(seed=False):
    """Initialize the database and optionally seed it with sample data"""
    db = ContactDatabase()
    if seed:
        print("Seeding database with sample contacts...")
        db.seed_sample_data()
        print("Database seeded successfully!")
    return db

# Initialize app with config
config = get_config()
app.config.from_object(config)

# Configure logging
if not os.path.exists(config.LOG_DIR):
    os.makedirs(config.LOG_DIR)

# Initialize the entity extractor and chatbot
extractor = AdvancedEntityExtractor()
chatbot = Chatbot(extractor)

# Initialize Microsoft Graph client and meeting database
graph_client = GraphClient(config)
meeting_db = MeetingDatabase()

@app.route('/')
def index():
    """Render the main chat interface"""
    # Generate a unique session ID if not present
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['chat_history'] = []
        chatbot.reset_context(session['session_id'])
        
        # Force session to be saved
        session.modified = True
    
    # Check if user is connected to Microsoft
    ms_session = meeting_db.get_session(session['session_id'])
    is_connected = bool(ms_session)
    
    return render_template('index.html', ms_connected=is_connected)

@app.route('/message', methods=['POST'])
def message():
    """Process incoming messages and return chatbot response"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'response': 'Please enter a message.'})
    
    # Get session ID or create one
    session_id = session.get('session_id', str(uuid.uuid4()))
    if 'session_id' not in session:
        session['session_id'] = session_id
        session['chat_history'] = []
        chatbot.reset_context(session_id)
        session.modified = True
    
    # Process the message and get response
    bot_response, entities = chatbot.process_message(user_message, session_id)
    
    # Update chat history
    chat_history = session.get('chat_history', [])
    chat_history.append({
        'user': user_message,
        'bot': bot_response,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    session['chat_history'] = chat_history
    session.modified = True
    
    # Check if context is complete and create Microsoft meeting if connected
    is_complete = chatbot.is_context_complete(session_id)
    
    # If complete and not already created, create Microsoft meeting
    if is_complete:
        context = chatbot.get_context(session_id)
        
        # Check if user is connected to Microsoft
        ms_session = meeting_db.get_session(session_id)
        user_id = session.get('user_id')
        
        if user_id and ms_session and not meeting_db.get_meeting(session_id):
            # Convert context to meeting data
            meeting_data = prepare_meeting_data_from_context(context)
            
            # Create meeting in Microsoft Graph
            try:
                created_meeting = graph_client.create_meeting(user_id, meeting_data)
                
                # Check if meeting was created successfully and is a dictionary
                if created_meeting and isinstance(created_meeting, dict) and created_meeting.get('id'):
                    # Save meeting information in database
                    meeting_db.save_meeting(session_id, session_id, created_meeting)
                    
                    # Since we're not creating Teams meetings, don't try to get the Teams link
                    # Just append a success message about the calendar appointment
                    bot_response += "\n\nI've added the meeting to your calendar."
                else:
                    # Handle meeting creation failure
                    error_msg = created_meeting.get('error', 'Unknown error') if isinstance(created_meeting, dict) else 'Failed to create meeting'
                    app.logger.error(f"Failed to create meeting: {error_msg}")
                    
                    # If it's an authentication issue, suggest reconnecting
                    if isinstance(created_meeting, dict) and ("token" in str(error_msg).lower() or "auth" in str(error_msg).lower()):
                        bot_response += "\n\nI couldn't create the calendar appointment. Please click 'Connect to Microsoft' to reauthorize calendar access."
                    else:
                        bot_response += "\n\nI couldn't create the calendar appointment due to a technical issue. Please try again later."
            except Exception as e:
                app.logger.error(f"Exception creating meeting: {e}", exc_info=True)
                bot_response += "\n\nI couldn't create the Microsoft Teams meeting due to a technical error. Please try again later."
                
        elif not user_id and is_complete:
            # User not authenticated, add login message
            bot_response += "\n\nTo create this meeting in your Microsoft calendar, please click 'Connect to Microsoft' to authorize access."
    
    # Return the response
    return jsonify({
        'response': bot_response,
        'entities': entities,
        'complete': is_complete
    })
    
@app.route('/reset', methods=['POST'])
def reset():
    """Reset the chat session"""
    session_id = str(uuid.uuid4())
    old_session_id = session.get('session_id')
    
    session['session_id'] = session_id
    session['chat_history'] = []
    session.modified = True
    
    chatbot.reset_context(session_id)
    
    # Delete any existing Microsoft meetings for this session
    if old_session_id:
        meeting_db.delete_meeting(old_session_id)
    
    return jsonify({
        'response': 'Chat session has been reset. How can I help you schedule something?',
        'entities': {},
        'complete': False
    })

@app.route('/export', methods=['GET'])
def export_session():
    """Export the current session data as JSON"""
    if 'session_id' not in session:
        return jsonify({'error': 'No active session'})
    
    session_id = session['session_id']
    context = chatbot.get_context(session_id)
    history = session.get('chat_history', [])
    
    # Get Microsoft meeting information if available
    meeting_info = meeting_db.get_meeting(session_id)
    
    return jsonify({
        'session_id': session_id,
        'context': context,
        'history': history,
        'meeting': meeting_info
    })

@app.route('/contacts', methods=['GET'])
def list_contacts():
    """List all contacts in the database"""
    contacts = chatbot.contact_db.get_all_contacts()
    return render_template('contacts.html', contacts=contacts)

@app.route('/contacts/add', methods=['GET', 'POST'])
def add_contact():
    """Add a new contact to the database"""
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        
        if first_name and last_name and email:
            success = chatbot.contact_db.add_contact(first_name, last_name, email)
            
            if success:
                return redirect(url_for('list_contacts'))
            else:
                return render_template('add_contact.html', error="Failed to add contact. Email may already exist.")
        else:
            return render_template('add_contact.html', error="All fields are required.")
    
    return render_template('add_contact.html')

@app.route('/contacts/delete/<int:contact_id>', methods=['POST'])
def delete_contact(contact_id):
    """Delete a contact from the database"""
    chatbot.contact_db.delete_contact(contact_id)
    return redirect(url_for('list_contacts'))

@app.route('/contacts/edit/<int:contact_id>', methods=['GET', 'POST'])
def edit_contact(contact_id):
    """Edit a contact in the database"""
    # Find the contact
    contacts = chatbot.contact_db.get_all_contacts()
    contact = next((c for c in contacts if c['id'] == contact_id), None)
    
    if not contact:
        return redirect(url_for('list_contacts'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        
        if first_name and last_name and email:
            success = chatbot.contact_db.update_contact(
                contact_id,
                first_name=first_name,
                last_name=last_name,
                email=email
            )
            
            if success:
                return redirect(url_for('list_contacts'))
            else:
                return render_template('edit_contact.html', contact=contact, error="Failed to update contact.")
        else:
            return render_template('edit_contact.html', contact=contact, error="All fields are required.")
    
    return render_template('edit_contact.html', contact=contact)

# Microsoft Graph authentication routes
@app.route('/auth/connect')
def connect_microsoft():
    """Generate Microsoft auth URL and redirect user"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    # Generate Microsoft auth URL (ignoring state)
    auth_url, _, _ = graph_client.get_auth_url()

    # Log the auth URL for debugging
    app.logger.info("Redirecting to Microsoft authentication.")

    try:
        # Redirect to Microsoft login
        return redirect(auth_url)
    except Exception as e:
        app.logger.error(f"Error generating auth URL: {e}", exc_info=True)
        return render_template('error.html', message="An error occurred during authentication setup. Please try again.")


@app.route('/auth/callback')
def auth_callback():
    """Handle Microsoft auth callback"""

    # Check for error in the callback
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    if error:
        app.logger.error(f"OAuth error: {error} - {error_description}")
        return render_template('error.html', message=f"Authentication error: {error_description}")

    # Get authorization code
    code = request.args.get('code')
    if not code:
        app.logger.error("No authorization code received")
        return render_template('error.html', message="No authorization code received. Authentication failed.")

    try:
        # Exchange code for tokens
        token_info = graph_client.get_token_from_code(code)

        if not token_info.get('success'):
            app.logger.error(f"Failed to get access token: {token_info.get('error')}")
            return render_template('error.html', 
                message=f"Failed to get access token: {token_info.get('error_description', 'Unknown error')}")

        # Store user ID in session
        user_id = token_info.get('user_id')
        if not user_id:
            app.logger.error("No user ID returned from token exchange")
            return render_template('error.html', message="Failed to get user information. Authentication failed.")

        # Save session information
        session_id = session.get('session_id')
        meeting_db.save_session(session_id, {"id": user_id}, {"access_token": "stored_in_graph_client"})

        # Store user_id in session for easy access
        session['user_id'] = user_id

        # Force session to be saved
        session.modified = True

        app.logger.info(f"Authentication successful for user_id: {user_id}")

        # Redirect to home page
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Exception during authentication: {e}", exc_info=True)
        return render_template('error.html', message="An unexpected error occurred during authentication. Please try again.")


@app.route('/auth/disconnect')
def disconnect_microsoft():
    """Disconnect from Microsoft Graph"""
    session_id = session.get('session_id')
    
    try:
        # Remove user_id from session
        if 'user_id' in session:
            session.pop('user_id')
        
        # Delete Microsoft session
        meeting_db.delete_session(session_id)
        app.logger.info(f"Disconnected Microsoft session for {session_id}")
        
        # Redirect to home page
        return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"Error during disconnect: {e}", exc_info=True)
        # Still redirect even if there was an error
        return redirect(url_for('index'))

@app.route('/meeting/status')
def meeting_status():
    """Get Microsoft meeting status for current session"""
    session_id = session.get('session_id')
    
    # Check if user is connected to Microsoft
    ms_session = meeting_db.get_session(session_id)
    is_connected = bool(ms_session)
    
    # Get meeting information if available
    meeting_info = meeting_db.get_meeting(session_id) if is_connected else {}
    has_meeting = bool(meeting_info)
    
    # Get Teams meeting link if available
    teams_link = meeting_info.get('online_meeting_url') if has_meeting else None
    
    return jsonify({
        'connected': is_connected,
        'has_meeting': has_meeting,
        'teams_link': teams_link
    })

@app.route('/meeting/delete', methods=['POST'])
def delete_meeting():
    """Delete Microsoft meeting for current session"""
    session_id = session.get('session_id')
    user_id = session.get('user_id')
    
    # Check if user is connected to Microsoft
    ms_session = meeting_db.get_session(session_id)
    if not ms_session or not user_id:
        return jsonify({'success': False, 'message': 'Not connected to Microsoft'})
    
    # Get Microsoft meeting ID
    ms_meeting_id = meeting_db.get_ms_meeting_id(session_id)
    if not ms_meeting_id:
        return jsonify({'success': False, 'message': 'No meeting found'})
    
    # Delete meeting in Microsoft Graph
    success = graph_client.delete_meeting(user_id, ms_meeting_id)
    
    if success:
        # Delete meeting from database
        meeting_db.delete_meeting(session_id)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Failed to delete meeting in Microsoft'})

# Debug routes
@app.route('/debug/session')
def debug_session():
    """Debug endpoint to view session contents"""
    if app.debug:
        return jsonify({
            'session_data': {k: v for k, v in session.items()},
            'session_id': session.get('session_id'),
            'ms_auth_state': session.get('ms_auth_state'),
            'user_id': session.get('user_id')
        })
    return "Debugging not available in production", 403

@app.route('/debug/reset-session')
def debug_reset_session():
    """Debug endpoint to reset the session"""
    if app.debug:
        session.clear()
        return jsonify({'message': 'Session cleared'})
    return "Debugging not available in production", 403

@app.route('/debug/ms-config')
def debug_ms_config():
    """Debug endpoint to view Microsoft Graph configuration (development only)"""
    if app.debug:
        # Don't show the actual secret, just whether it exists
        has_client_secret = bool(app.config.get('MICROSOFT_CLIENT_SECRET', ''))
        
        return jsonify({
            'client_id': app.config.get('MICROSOFT_CLIENT_ID', 'Not set'),
            'client_secret_present': has_client_secret,
            'authority': graph_client.authority,
            'redirect_uri': graph_client.redirect_uri,
            'scopes': graph_client.scope
        })
    return "Debugging not available in production", 403

@app.route('/debug/ms-token-test')
def debug_ms_token_test():
    """Debug endpoint to test Microsoft token acquisition"""
    if not app.debug:
        return "Debugging not available in production", 403
    
    try:
        # Generate a test auth URL
        auth_url, state, code_verifier = graph_client.get_auth_url()
        
        # Check basic connectivity and config
        config_status = {
            'client_id_set': bool(graph_client.client_id),
            'redirect_uri_set': bool(graph_client.redirect_uri),
            'scopes_set': bool(graph_client.scope),
            'auth_url_generated': bool(auth_url)
        }
        
        return jsonify({
            'status': 'Configuration test',
            'config_status': config_status,
            'auth_url_preview': auth_url[:100] + '...' if auth_url else None
        })
    except Exception as e:
        app.logger.error(f"Error in token test: {e}", exc_info=True)
        return jsonify({
            'status': 'Error testing MSAL configuration',
            'error': str(e)
        }), 500

# Helper function to prepare meeting data from chat context
def prepare_meeting_data_from_context(context):
    """
    Convert chat context to Microsoft Graph meeting data format
    
    Args:
        context: Chat context with extracted entities
        
    Returns:
        Dict: Meeting data for Microsoft Graph API
    """
    # Get date, time, duration and attendees from context
    date = context.get('DATE', [''])[0]  # e.g., "2023-03-15"
    time = context.get('TIME', [''])[0]  # e.g., "3pm"
    duration = context.get('DURATION', [''])[0]  # e.g., "30 mins"
    attendees = context.get('ATTENDEE', [])
    
    # Get duration in minutes
    import re
    duration_minutes = 30  # Default to 30 minutes
    if duration:
        # Extract number from duration string
        duration_match = re.search(r'(\d+)', duration)
        if duration_match:
            num = int(duration_match.group(1))
            if 'hour' in duration:
                duration_minutes = num * 60
            else:
                duration_minutes = num
    
    # Extract email addresses from attendees
    email_addresses = graph_client.extract_emails_from_attendees(attendees)
    
    # Create basic meeting data
    meeting_data = {
        'subject': f"Meeting on {date} at {time}",
        'body': f"Meeting scheduled via Scheduling Assistant\n\nDate: {date}\nTime: {time}\nDuration: {duration}\nAttendees: {', '.join(attendees)}",
        'date': date,
        'time': time,
        'duration_minutes': duration_minutes,
        'attendees': email_addresses
    }
    
    return meeting_data

if __name__ == '__main__':
    args = parse_arguments()
    
    # Initialize and seed database if requested
    if args.seed_db:
        initialize_database(seed=True)
    
    app.run(debug=True)