#!/usr/bin/env python3
import datetime
import sys
import os

print(f"[{datetime.datetime.now()}] AttendanceTracker starting with PID: {os.getpid()} (before imports)",
      file=sys.stderr)

import requests
import socket
import time
import json
import logging
from logging.handlers import RotatingFileHandler
import configparser
import traceback
import atexit

# Setup paths
APP_SUPPORT = os.path.expanduser("~/Library/Application Support/AttendanceTracker")
LOG_DIR = os.path.join(APP_SUPPORT, 'Logs')
os.makedirs(LOG_DIR, exist_ok=True)
ATT_LOCK_FILE = os.path.join(APP_SUPPORT, 'attendance_tracker.lock')

# Log file for AttendanceTracker
log_file = os.path.join(LOG_DIR, 'outputat.log')

# Configure logging
logger = logging.getLogger('AttendanceTracker')
logger.setLevel(logging.INFO)

# Clear existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Read logging config
config_file = os.path.join(APP_SUPPORT, 'logging.conf')
config = configparser.ConfigParser()
log_level = 'INFO'
max_bytes = 10 * 1024 * 1024

if os.path.exists(config_file):
    try:
        config.read(config_file)
        if 'logging' in config:
            log_level = config['logging'].get('level', 'INFO').upper()
            max_bytes = config['logging'].getint('max_size_mb', 10) * 1024 * 1024
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Failed to parse logging.conf: {e}", file=sys.stderr)
        if os.path.exists(ATT_LOCK_FILE):
            try:
                os.remove(ATT_LOCK_FILE)
            except OSError as e:
                print(f"[{datetime.datetime.now()}] Failed to remove lock file: {e}", file=sys.stderr)
        sys.exit(1)

# Set log level
logger.setLevel(getattr(logging, log_level, logging.INFO))

# Add rotating file handler
try:
    handler = RotatingFileHandler(log_file, mode='a', maxBytes=max_bytes, backupCount=1)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(handler)
except Exception as e:
    print(f"[{datetime.datetime.now()}] Failed to set up file logging: {e}", file=sys.stderr)

# Add stderr handler as fallback
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.INFO)
stderr_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
logger.addHandler(stderr_handler)

# Optional console handler for debugging
if os.environ.get('DEBUG'):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(console_handler)

logger.info("AttendanceTracker logging initialized at process start")


# Create lock file with PID
def create_lock_file():
    try:
        with open(ATT_LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
            f.flush()
            os.fsync(f.fileno())  # Ensure the write is flushed to disk
        logger.info(f"Created lock file {ATT_LOCK_FILE} with PID: {os.getpid()}")
    except Exception as e:
        logger.error(f"Failed to create lock file {ATT_LOCK_FILE}: {str(e)}")
        sys.exit(1)


# Ensure lock file is removed on exit
def cleanup_lock():
    if os.path.exists(ATT_LOCK_FILE):
        logger.info("Cleaning up attendance_tracker.lock on exit")
        try:
            os.remove(ATT_LOCK_FILE)
        except OSError as e:
            logger.error(f"Failed to remove lock file on exit: {e}")


atexit.register(cleanup_lock)

# Create lock file immediately after logging setup
create_lock_file()


def get_config():
    config_path = os.path.join(LOG_DIR, 'config.json')
    if not os.path.exists(config_path):
        config_path = os.path.join(APP_SUPPORT, 'config.json')

    logger.info(f"Attempting to load config from: {config_path}")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading config: {str(e)} with traceback: {traceback.format_exc()}")
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
    version = config.get('version', '1.0.0')
    for attempt in range(max_attempts):
        try:
            client_time = datetime.datetime.now()
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
                logger.info(f"Success: Server accepted check-in at {datetime.datetime.now()}")
                save_success_date()
                logger.handlers[0].flush()
                return True
            elif response.status_code == 208:
                logger.info(f"Server telling me that already checked in today at {datetime.datetime.now()}")
                save_success_date()
                logger.handlers[0].flush()
                return True
            else:
                logger.error(f"Unexpected response: {response.status_code}")

        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection failed on attempt {attempt + 1}/{max_attempts}: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error on attempt {attempt + 1}/{max_attempts}: {str(e)} with traceback: {traceback.format_exc()}")

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
        logger.error(f"Error reading last success date: {str(e)} with traceback: {traceback.format_exc()}")
    return None


def save_success_date():
    date_file = os.path.join(LOG_DIR, 'last_success.txt')
    try:
        os.makedirs(os.path.dirname(date_file), exist_ok=True)
        with open(date_file, 'w') as f:
            f.write(datetime.datetime.now().strftime('%Y-%m-%d'))
    except Exception as e:
        logger.error(f"Error saving success date: {str(e)} with traceback: {traceback.format_exc()}")


def main():
    logger.info(f"AttendanceTracker starting up in main with PID: {os.getpid()}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Log file path: {log_file}")
    try:
        config = get_config()
        logger.info("Config loaded, checking last success date")
        time.sleep(config['application']['startup_delay_seconds'])

        last_date = get_last_success_date()
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        if last_date == today:
            logger.info(f"I found that I already checked in today at {datetime.datetime.now()}")
            logger.handlers[0].flush()
            sys.exit(0)

        if try_connect_with_retry(config):
            save_success_date()
            sys.exit(0)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error in main: {str(e)} with traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()