import logging
import os
from datetime import datetime

# Configure logging
def setup_logging(log_level=logging.INFO, log_file=None):
    """
    Set up structured logging for the application.
    
    Args:
        log_level: The logging level (default: INFO)
        log_file: Path to log file (optional, defaults to console only)
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger

def get_logger(name):
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

# Pre-configured logger instances
app_logger = get_logger('app')
db_logger = get_logger('database')
security_logger = get_logger('security')
payment_logger = get_logger('payment')

# Convenience functions for different log levels
def log_info(logger, message, **kwargs):
    """Log an info message with optional structured data."""
    if kwargs:
        message = f"{message} | Data: {kwargs}"
    logger.info(message)

def log_warning(logger, message, **kwargs):
    """Log a warning message with optional structured data."""
    if kwargs:
        message = f"{message} | Data: {kwargs}"
    logger.warning(message)

def log_error(logger, message, **kwargs):
    """Log an error message with optional structured data."""
    if kwargs:
        message = f"{message} | Data: {kwargs}"
    logger.error(message)

def log_debug(logger, message, **kwargs):
    """Log a debug message with optional structured data."""
    if kwargs:
        message = f"{message} | Data: {kwargs}"
    logger.debug(message)

# Initialize logging on module import
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_FILE = os.environ.get('LOG_FILE', None)

# Map string log levels to constants
log_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

setup_logging(log_level=log_level_map.get(LOG_LEVEL, logging.INFO), log_file=LOG_FILE)