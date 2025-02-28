# Symlink or copy from MacOS with minimal changes


import requests
import socket
import time
from datetime import datetime
import json
import os
import sys
import logging
import uuid

# Setup logger
logger = logging.getLogger('AttendanceTracker')

# Setup paths
APP_SUPPORT = os.path.join(os.environ['APPDATA'], 'AttendanceTracker')
LOG_DIR = os.path.join(APP_SUPPORT, 'Logs')

def get_config():
    config_path = os.path.join(APP_SUPPORT, 'config.json')
    # Setup logging
    logging.basicConfig(
        filename=os.path.join(LOG_DIR, 'output.log'),
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] AttendanceTracker: %(message)s'
    )
    
    error_handler = logging.FileHandler(os.path.join(LOG_DIR, 'error.log'))
    error_handler.setLevel(logging.ERROR)
    logging.getLogger().addHandler(error_handler)

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error reading config: {str(e)}")
        sys.exit(1)

def get_hostname():
    hostname = socket.gethostname()
    # Take everything before the first dot
    return hostname.split('.')[0]

def validate_server_config(config):
    if not config['server']['url'].startswith('https://'):
        logging.warning("Using insecure HTTP connection")
    
    try:
        socket.gethostbyname(config['server']['url'].split('://')[1].split(':')[0])
    except:
        logging.error("Cannot resolve server hostname")
        return False
    return True

def get_machine_id():
    # Use more reliable machine identification
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))

def try_connect_with_retry(config, max_attempts=None, delay_seconds=None):
    url = config['server']['url'] + '/checkin'
    hostname = get_hostname()
    
    logger.info(f"Starting connection attempts with hostname: {hostname}")
    logger.info(f"Server URL: {url}")
    logger.info(f"Max attempts: {max_attempts}, Delay: {delay_seconds} seconds")
    
    max_attempts = max_attempts or config['server'].get('max_retry_attempts', 10)
    delay_seconds = delay_seconds or config['server'].get('retry_delay_seconds', 60)
    
    for attempt in range(max_attempts):
        try:
            client_time = datetime.now()
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Sending request...")
            logger.info(f"Request data: hostname={hostname}, time={client_time.isoformat()}")
            response = requests.post(url, 
                                    json={
                                        "hostname": hostname,
                                        "client_time": client_time.isoformat()
                                    },
                                    timeout=config['server']['timeout_seconds'])
            
            if response.status_code == 200:
                logger.info(f"Success: Server accepted check-in at {datetime.now()}")
                save_success_date()
                logger.handlers[0].flush()  # Force flush
                sys.exit(0)
            elif response.status_code == 208:
                logger.info(f"Server telling me that already checked in today at {datetime.now()}")
                save_success_date()
                logger.handlers[0].flush()
                sys.exit(0)
            else:
                logger.error(f"Unexpected response: {response.status_code}")
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed on attempt {attempt + 1}/{max_attempts}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}/{max_attempts}: {str(e)}")
            
        if attempt < max_attempts - 1:
            logger.info(f"Waiting {delay_seconds} seconds before next attempt...")
            time.sleep(delay_seconds)
            
    logger.error(f"Failed to connect after {max_attempts} attempts")
    return False

def get_last_success_date():
    date_file = os.path.join(LOG_DIR, 'last_success.txt')
    try:
        if os.path.exists(date_file):
            with open(date_file, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading last success date: {str(e)}")
    return None

def save_success_date():
    date_file = os.path.join(LOG_DIR, 'last_success.txt')
    try:
        os.makedirs(os.path.dirname(date_file), exist_ok=True)
        with open(date_file, 'w') as f:
            f.write(datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        logger.error(f"Error saving success date: {str(e)}")

def main():
    logger.info("AttendanceTracker starting up in main")
    try:
        config = get_config()
        logger.info("Config loaded, checking last success date")
        time.sleep(config['application']['startup_delay_seconds'])
        
        last_date = get_last_success_date()
        today = datetime.now().strftime('%Y-%m-%d')
        if last_date == today:
            logger.info(f" I found that I already checked in today at {datetime.now()}")
            logger.handlers[0].flush()
            sys.exit(0)
        
        if try_connect_with_retry(config):
            save_success_date()
            sys.exit(0)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()