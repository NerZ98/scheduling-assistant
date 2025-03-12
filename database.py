import os
import sqlite3
import logging
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path

class ContactDatabase:
    """
    Database handler for storing and retrieving contact information
    """
    def __init__(self, db_path='contacts.db', logger=None):
        """
        Initialize the contact database
        
        Args:
            db_path (str): Path to the SQLite database file
            logger (logging.Logger, optional): Logger instance
        """
        self.db_path = db_path
        
        # Setup logging
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger('ContactDatabase')
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
            self.logger.info(f"Initializing database at {self.db_path}")
            # Ensure the directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
                
            # Create connection and table
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create contacts table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            conn.commit()
            conn.close()
            self.logger.info("Database initialized successfully")
        
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}", exc_info=True)
            raise
    
    def add_contact(self, first_name: str, last_name: str, email: str) -> bool:
        """
        Add a new contact to the database
        
        Args:
            first_name (str): First name
            last_name (str): Last name
            email (str): Email address
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if email already exists
            cursor.execute("SELECT email FROM contacts WHERE email = ?", (email,))
            if cursor.fetchone():
                self.logger.warning(f"Contact with email {email} already exists")
                conn.close()
                return False
            
            # Insert new contact
            cursor.execute(
                "INSERT INTO contacts (first_name, last_name, email) VALUES (?, ?, ?)",
                (first_name, last_name, email)
            )
            
            conn.commit()
            conn.close()
            self.logger.info(f"Added contact: {first_name} {last_name} ({email})")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding contact: {e}", exc_info=True)
            return False
    
    def find_contacts_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Find contacts by name (first or last)
        
        Args:
            name (str): Name to search for
            
        Returns:
            List[Dict]: List of matching contacts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            # Convert name to lowercase for case-insensitive comparison
            name = name.strip().lower()
            self.logger.debug(f"Searching for name (lowercase): '{name}'")
            
            # Split name into first and last components if possible
            name_parts = name.split()
            
            if len(name_parts) > 1:
                # We have potentially both first and last name
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                self.logger.debug(f"Searching for first_name={first_name}, last_name={last_name}")
                
                # Use LOWER() function for case-insensitive search on first and last name
                cursor.execute("""
                    SELECT * FROM contacts 
                    WHERE (LOWER(first_name) LIKE ? AND LOWER(last_name) LIKE ?)
                """, (first_name, last_name))
            else:
                # We only have one name part, search in both fields with case-insensitive matching
                search_term = f"%{name}%"
                self.logger.debug(f"Searching for name={search_term} in first or last name")
                
                cursor.execute("""
                    SELECT * FROM contacts 
                    WHERE LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                """, (search_term, search_term))
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            self.logger.info(f"Found {len(results)} contacts matching '{name}'")
            return results
        
        except Exception as e:
            self.logger.error(f"Error finding contacts: {e}", exc_info=True)
            return []
        
    def find_contacts_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Find a contact by their email
        
        Args:
            email (str): Email to search for
            
        Returns:
            Dict or None: Contact information if found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM contacts WHERE email = ?", (email,))
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                self.logger.info(f"Found contact with email {email}")
                return dict(result)
            else:
                self.logger.info(f"No contact found with email {email}")
                return None
        
        except Exception as e:
            self.logger.error(f"Error finding contact by email: {e}", exc_info=True)
            return None
    
    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """
        Get all contacts from the database
        
        Returns:
            List[Dict]: List of all contacts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM contacts ORDER BY last_name, first_name")
            results = [dict(row) for row in cursor.fetchall()]
            
            conn.close()
            
            self.logger.info(f"Retrieved {len(results)} contacts")
            return results
        
        except Exception as e:
            self.logger.error(f"Error retrieving contacts: {e}", exc_info=True)
            return []
    
    def update_contact(self, contact_id: int, **kwargs) -> bool:
        """
        Update a contact's information
        
        Args:
            contact_id (int): Contact ID
            **kwargs: Fields to update (first_name, last_name, email)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            allowed_fields = {'first_name', 'last_name', 'email'}
            update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
            
            if not update_fields:
                self.logger.warning("No valid fields provided for update")
                return False
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build the SQL query
            set_clause = ", ".join(f"{field} = ?" for field in update_fields)
            values = list(update_fields.values())
            values.append(contact_id)
            
            cursor.execute(
                f"UPDATE contacts SET {set_clause} WHERE id = ?",
                values
            )
            
            if cursor.rowcount == 0:
                self.logger.warning(f"No contact found with ID {contact_id}")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Updated contact ID {contact_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error updating contact: {e}", exc_info=True)
            return False
    
    def delete_contact(self, contact_id: int) -> bool:
        """
        Delete a contact from the database
        
        Args:
            contact_id (int): Contact ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            
            if cursor.rowcount == 0:
                self.logger.warning(f"No contact found with ID {contact_id}")
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Deleted contact ID {contact_id}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error deleting contact: {e}", exc_info=True)
            return False
    
    def seed_sample_data(self) -> bool:
        """
        Seed the database with sample data for testing
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Sample data with some duplicate names
            sample_contacts = [
                ("John", "Smith", "john.smith@example.com"),
                ("Jane", "Doe", "jane.doe@example.com"),
                ("Michael", "Johnson", "michael.johnson@example.com"),
                ("Emily", "Davis", "emily.davis@example.com"),
                ("John", "Smith", "john.smith2@example.com"),  # Duplicate name
                ("Sarah", "Wilson", "sarah.wilson@example.com"),
                ("David", "Brown", "david.brown@example.com"),
                ("Jennifer", "Miller", "jennifer.miller@example.com"),
                ("Robert", "Jones", "robert.jones@example.com"),
                ("Jessica", "Garcia", "jessica.garcia@example.com"),
                ("Rutuj", "Desai", "rutuj.desai@example.com"),
                ("Rutuj", "Desai", "rutuj.desai2@example.com"),  # Duplicate name
                ("John", "Doe", "john.doe@example.com"),
                ("Mary", "Johnson", "mary.johnson@example.com")
            ]
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Add sample contacts
            for first_name, last_name, email in sample_contacts:
                # Skip if email already exists
                cursor.execute("SELECT email FROM contacts WHERE email = ?", (email,))
                if cursor.fetchone():
                    continue
                
                cursor.execute(
                    "INSERT INTO contacts (first_name, last_name, email) VALUES (?, ?, ?)",
                    (first_name, last_name, email)
                )
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Seeded database with {len(sample_contacts)} sample contacts")
            return True
        
        except Exception as e:
            self.logger.error(f"Error seeding sample data: {e}", exc_info=True)
            return False