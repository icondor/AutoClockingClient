#!/usr/bin/env python3
import requests
import socket
import time
from datetime import datetime
import json
import os
import sys
import logging

# Ensure logging works in frozen environment
log_dir = os.path.expanduser('~/Library/Application Support/AttendanceTracker')
os.makedirs(log_dir, exist_ok=True)  # Ensure directory exists
log_file = os.path.join(log_dir, 'attendanceoutput.log')
error_file = os.path.join(log_dir, 'attendanceerror.log')

# Explicitly create log files to avoid permission issues
open(log_file, 'a').close()
open(error_file, 'a').close()
os.chmod(log_file, 0o666)  # Ensure writable
os.chmod(error_file, 0o666)

# Use a custom logger to avoid conflicts
logger = logging.getLogger('AttendanceTracker')
logger.setLevel(logging.INFO)

# Clear any inherited handlers
logger.handlers = []

# File handlers with explicit paths
output_handler = logging.FileHandler(log_file)
output_handler.setLevel(logging.INFO)
output_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] AttendanceTracker: %(message)s'))
logger.addHandler(output_handler)

error_handler = logging.FileHandler(error_file)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] AttendanceTracker: %(message)s'))
logger.addHandler(error_handler)

# Optional: Add console output for debugging (remove in production)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] AttendanceTracker: %(message)s'))
logger.addHandler(console_handler)

logger.info("AttendanceTracker process starting")

def get_config():
    config_path = os.path.join(log_dir, 'config.json')
    logger.info(f"Attempting to load config from: {config_path}")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading config: {str(e)}")
        sys.exit(1)

def get_hostname():
    hostname = socket.gethostname()
    return hostname.split('.')[0]

def try_connect_with_retry(config, max_attempts=None, delay_seconds=None):
    url = config['server']['url'] + '/checkin'
    hostname = get_hostname()
    
    logger.info(f"Starting connection attempts with hostname: {hostname}")
    logger.info(f"Server URL: {url}")
    logger.info(f"Max attempts: {max_attempts}, Delay: {delay_seconds} seconds")
    
    max_attempts = max_attempts or config['server'].get('max_retry_attempts', 10)
    delay_seconds = delay_seconds or config['server'].get('retry_delay_seconds', 60)
    version = config.get('version', '1.0.0')  # Default to 1.0.0 if not specif
    for attempt in range(max_attempts):
        try:
            client_time = datetime.now()
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Sending request...")
            logger.info(f"Request data: hostname={hostname}, time={client_time.isoformat()}")
            response = requests.post(url, 
                                    json={
                                        "hostname": hostname,
                                        "client_time": client_time.isoformat(),
                                        "version": version
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
    date_file = os.path.join(log_dir, 'last_success.txt')
    try:
        if os.path.exists(date_file):
            with open(date_file, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Error reading last success date: {str(e)}")
    return None

def save_success_date():
    date_file = os.path.join(log_dir, 'last_success.txt')
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