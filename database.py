import logging
from typing import List, Dict, Tuple, Optional, Any
import mysql.connector
from mysql.connector import pooling

class ContactDatabase:
    """
    Database handler for retrieving contact information from OrangeHRM MySQL database
    """
    def __init__(self, config=None, logger=None):
        """
        Initialize the contact database connection to OrangeHRM
        
        Args:
            config: Application configuration containing MySQL settings
            logger (logging.Logger, optional): Logger instance
        """
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
                
        # Store config
        self.config = config
        
        # Initialize connection pool
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize a MySQL connection pool"""
        try:
            self.logger.info("Initializing MySQL connection pool")
            
            # Get MySQL connection parameters from config
            db_config = {
                'host': self.config.MYSQL_HOST,
                'user': self.config.MYSQL_USER,
                'password': self.config.MYSQL_PASSWORD,
                'database': self.config.MYSQL_DATABASE,
                'pool_name': 'orangehrm_pool',
                'pool_size': 5
            }
            
            # Initialize the connection pool
            self.connection_pool = mysql.connector.pooling.MySQLConnectionPool(**db_config)
            self.logger.info("MySQL connection pool initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing MySQL connection pool: {e}", exc_info=True)
            raise
    
    def _get_connection(self):
        """Get a connection from the pool"""
        try:
            return self.connection_pool.get_connection()
        except Exception as e:
            self.logger.error(f"Error getting connection from pool: {e}", exc_info=True)
            raise
    
    def add_contact(self, first_name: str, last_name: str, email: str) -> bool:
        """
        This method is disabled as we are in read-only mode for OrangeHRM database
        
        Args:
            first_name (str): First name
            last_name (str): Last name
            email (str): Email address
            
        Returns:
            bool: Always False, indicating operation not supported
        """
        self.logger.warning("add_contact operation not supported in read-only mode")
        return False
    
    def find_contacts_by_name(self, name: str) -> List[Dict[str, Any]]:
        """
        Find contacts in OrangeHRM database by name (first or last)
        
        Args:
            name (str): Name to search for
            
        Returns:
            List[Dict]: List of matching contacts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Convert name to lowercase for case-insensitive comparison
            name = name.strip().lower()
            self.logger.debug(f"Searching for name (lowercase): '{name}'")
            
            # Split name into components
            name_parts = name.split()
            
            results = []
            
            if len(name_parts) > 1:
                # We have potentially both first and last name
                first_name = name_parts[0]
                last_name = name_parts[-1]
                
                self.logger.debug(f"Searching for first_name={first_name}, last_name={last_name}")
                
                # Try with exact first and last name
                query = """
                    SELECT 
                        employee_id as id,
                        emp_firstname as first_name, 
                        emp_lastname as last_name, 
                        emp_work_email as email 
                    FROM hs_hr_employee 
                    WHERE (LOWER(emp_firstname) = %s AND LOWER(emp_lastname) = %s)
                """
                cursor.execute(query, (first_name, last_name))
                
                results = cursor.fetchall()
                
                # If no exact match, try with LIKE
                if not results:
                    query = """
                        SELECT 
                            employee_id as id,
                            emp_firstname as first_name, 
                            emp_lastname as last_name, 
                            emp_work_email as email 
                        FROM hs_hr_employee 
                        WHERE (LOWER(emp_firstname) LIKE %s AND LOWER(emp_lastname) LIKE %s)
                    """
                    cursor.execute(query, (f"{first_name}%", f"{last_name}%"))
                    
                    results = cursor.fetchall()
            
            # If no results yet, try individual name parts
            if not results:
                for part in name_parts:
                    # Skip very short parts
                    if len(part) <= 1:
                        continue
                        
                    search_term = f"{part}%"
                    
                    # Search in both first_name and last_name
                    query = """
                        SELECT 
                            employee_id as id,
                            emp_firstname as first_name, 
                            emp_lastname as last_name, 
                            emp_work_email as email 
                        FROM hs_hr_employee 
                        WHERE LOWER(emp_firstname) LIKE %s OR LOWER(emp_lastname) LIKE %s
                    """
                    cursor.execute(query, (search_term, search_term))
                    
                    part_results = cursor.fetchall()
                    if part_results:
                        # Add unique results to the main results list
                        for contact in part_results:
                            if contact not in results:
                                results.append(contact)
            
            # If still no results, try fuzzy matching with the whole name
            if not results:
                # Use a more permissive LIKE pattern
                search_term = f"%{name}%"
                query = """
                    SELECT 
                        employee_id as id,
                        emp_firstname as first_name, 
                        emp_lastname as last_name, 
                        emp_work_email as email 
                    FROM hs_hr_employee 
                    WHERE LOWER(CONCAT(emp_firstname, ' ', emp_lastname)) LIKE %s
                    OR LOWER(CONCAT(emp_lastname, ' ', emp_firstname)) LIKE %s
                """
                cursor.execute(query, (search_term, search_term))
                
                results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # Filter out results without email addresses
            filtered_results = [r for r in results if r.get('email')]
            
            self.logger.info(f"Found {len(filtered_results)} contacts matching '{name}'")
            return filtered_results
        
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
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT 
                    employee_id as id,
                    emp_firstname as first_name, 
                    emp_lastname as last_name, 
                    emp_work_email as email 
                FROM hs_hr_employee 
                WHERE emp_work_email = %s
            """
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result:
                self.logger.info(f"Found contact with email {email}")
                return result
            else:
                self.logger.info(f"No contact found with email {email}")
                return None
        
        except Exception as e:
            self.logger.error(f"Error finding contact by email: {e}", exc_info=True)
            return None
    
    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """
        Get all contacts from the database who have email addresses
        
        Returns:
            List[Dict]: List of all contacts
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT 
                    employee_id as id,
                    emp_firstname as first_name, 
                    emp_lastname as last_name, 
                    emp_work_email as email 
                FROM hs_hr_employee 
                WHERE emp_work_email IS NOT NULL AND emp_work_email != ''
                ORDER BY emp_lastname, emp_firstname
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            self.logger.info(f"Retrieved {len(results)} contacts")
            return results
        
        except Exception as e:
            self.logger.error(f"Error retrieving contacts: {e}", exc_info=True)
            return []
    
    def update_contact(self, contact_id: int, **kwargs) -> bool:
        """
        This method is disabled as we are in read-only mode for OrangeHRM database
        
        Args:
            contact_id (int): Contact ID
            **kwargs: Fields to update (first_name, last_name, email)
            
        Returns:
            bool: Always False, indicating operation not supported
        """
        self.logger.warning("update_contact operation not supported in read-only mode")
        return False
    
    def delete_contact(self, contact_id: int) -> bool:
        """
        This method is disabled as we are in read-only mode for OrangeHRM database
        
        Args:
            contact_id (int): Contact ID
            
        Returns:
            bool: Always False, indicating operation not supported
        """
        self.logger.warning("delete_contact operation not supported in read-only mode")
        return False
    
    def seed_sample_data(self) -> bool:
        """
        This method is disabled as we are in read-only mode for OrangeHRM database
        
        Returns:
            bool: Always False, indicating operation not supported
        """
        self.logger.warning("seed_sample_data operation not supported in read-only mode")
        return False