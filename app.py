from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import argparse
from datetime import datetime
import uuid
import logging
from config import get_config
from extractor import AdvancedEntityExtractor
from chatbot import Chatbot
from database import ContactDatabase

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

# Initialize Flask app with config
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Ensure the logs directory exists
if not os.path.exists(config.LOG_DIR):
    os.makedirs(config.LOG_DIR)

# Initialize the entity extractor and chatbot
extractor = AdvancedEntityExtractor()
chatbot = Chatbot(extractor)

@app.route('/')
def index():
    """Render the main chat interface"""
    # Generate a unique session ID if not present
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['chat_history'] = []
        chatbot.reset_context(session['session_id'])
    
    return render_template('index.html')

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
    
    # Return the response
    return jsonify({
        'response': bot_response,
        'entities': entities,
        'complete': chatbot.is_context_complete(session_id)
    })

@app.route('/reset', methods=['POST'])
def reset():
    """Reset the chat session"""
    session_id = str(uuid.uuid4())
    session['session_id'] = session_id
    session['chat_history'] = []
    chatbot.reset_context(session_id)
    
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
    
    return jsonify({
        'session_id': session_id,
        'context': context,
        'history': history
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

if __name__ == '__main__':
    args = parse_arguments()
    
    # Initialize and seed database if requested
    if args.seed_db:
        initialize_database(seed=True)
    
    app.run(debug=True)