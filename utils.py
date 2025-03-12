import os
import logging
from datetime import datetime
import json
from typing import Dict, List, Any

def setup_logger(name: str, log_dir: str = 'logs', log_level: str = 'INFO') -> logging.Logger:
    """
    Configure a logger with file and console handlers
    
    Args:
        name (str): Logger name
        log_dir (str): Directory for log files
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        logging.Logger: Configured logger
    """
    # Create logs directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate unique log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_filename = os.path.join(log_dir, f'{name}_{timestamp}.log')
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Set level from string
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # File Handler with more detailed formatting
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def export_conversation(session_id: str, context: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    """
    Export conversation data to a JSON file
    
    Args:
        session_id (str): Session identifier
        context (Dict): Conversation context
        history (List): Chat history
    
    Returns:
        str: Path to the exported file
    """
    # Create exports directory if it doesn't exist
    export_dir = 'exports'
    os.makedirs(export_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(export_dir, f'conversation_{session_id}_{timestamp}.json')
    
    # Prepare data for export
    export_data = {
        'session_id': session_id,
        'timestamp': datetime.now().isoformat(),
        'context': context,
        'history': history
    }
    
    # Export to JSON file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    return filename

def format_duration(duration_str: str) -> str:
    """
    Format duration string for display
    
    Args:
        duration_str (str): Raw duration string (e.g., "30 mins")
    
    Returns:
        str: Formatted duration string
    """
    # Check if duration is in standard format
    if not duration_str:
        return ""
    
    # Extract number and unit
    import re
    match = re.match(r'(\d+)\s*(\w+)', duration_str)
    if not match:
        return duration_str
    
    number, unit = match.groups()
    
    # Standardize units
    if unit.lower() in ['min', 'mins', 'minute', 'minutes', 'm']:
        if int(number) == 1:
            return f"{number} minute"
        return f"{number} minutes"
    elif unit.lower() in ['hr', 'hrs', 'hour', 'hours', 'h']:
        if int(number) == 1:
            return f"{number} hour"
        return f"{number} hours"
    
    return duration_str

def format_date(date_str: str) -> str:
    """
    Format date string for display
    
    Args:
        date_str (str): Date string in yyyy-mm-dd format
    
    Returns:
        str: Formatted date string
    """
    if not date_str:
        return ""
    
    try:
        # Parse date string
        date = datetime.strptime(date_str, "%Y-%m-%d")
        # Format for display
        return date.strftime("%A, %B %d, %Y")
    except ValueError:
        # Return original if parsing fails
        return date_str

def format_time(time_str: str) -> str:
    """
    Format time string for display
    
    Args:
        time_str (str): Time string (e.g., "3pm" or "3:30pm")
    
    Returns:
        str: Formatted time string
    """
    if not time_str:
        return ""
    
    # Standardize AM/PM notation
    time_str = time_str.lower().replace(' ', '')
    
    # Check for standard format with colon
    if ':' in time_str:
        # Already in hh:mm format
        return time_str.upper()
    
    # Handle format like "3pm"
    import re
    match = re.match(r'(\d+)(am|pm)', time_str)
    if match:
        hour, period = match.groups()
        return f"{hour}:00 {period.upper()}"
    
    return time_str.upper()