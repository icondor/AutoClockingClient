import requests
import socket
import time
from datetime import datetime
import json
import os
import sys
import logging
import uuid
from logging.handlers import RotatingFileHandler
import configparser
from urllib.parse import urlparse

# Setup paths
APP_SUPPORT = os.path.join(os.environ['APPDATA'], 'AttendanceTracker')
LOG_DIR = os.path.join(APP_SUPPORT, 'Logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
power_monitor_log = os.path.join(LOG_DIR, 'attendancetracker.log')
logger = logging.getLogger()
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

config_file = os.path.join(os.path.dirname(sys.executable), 'logging.conf')
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
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"Failed to read logging config from {config_file}: {e}")

handler = RotatingFileHandler(power_monitor_log, mode='w', maxBytes=max_bytes, backupCount=0)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] AttendanceTracker: %(message)s'))
level = getattr(logging, log_level, logging.INFO)
logger.setLevel(level)
handler.setLevel(level)
logger.addHandler(handler)

# Resolve address with IPv4 preference, fallback to IPv6
def get_ip_address(host, port):
    try:
        # First try IPv4
        addrinfo = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        ip = addrinfo[0][4][0]
        logger.info(f"Resolved {host} to IPv4: {ip}")
        return ip, socket.AF_INET
    except socket.gaierror as e:
        logger.warning(f"IPv4 resolution failed for {host}: {str(e)}. Trying IPv6...")
        try:
            # Fallback to IPv6
            addrinfo = socket.getaddrinfo(host, port, socket.AF_INET6, socket.SOCK_STREAM)
            ip = addrinfo[0][4][0]
            logger.info(f"Resolved {host} to IPv6: {ip}")
            return f"[{ip}]", socket.AF_INET6
        except socket.gaierror as e2:
            logger.error(f"IPv6 resolution failed for {host}: {str(e2)}")
            raise

def get_config():
    config_path = os.path.join(APP_SUPPORT, 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading config: {str(e)}")
        sys.exit(1)

def get_hostname():
    hostname = socket.gethostname()
    return hostname.split('.')[0]

def validate_server_config(config):
    if not config['server']['url'].startswith('https://'):
        logger.warning("Using insecure HTTP connection")
    try:
        socket.gethostbyname(config['server']['url'].split('://')[1].split(':')[0].split('/')[0])
    except:
        logger.error("Cannot resolve server hostname")
        return False
    return True

def get_machine_id():
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))

def try_connect_with_retry(config, max_attempts=None, delay_seconds=None):
    base_url = config['server']['url'].split('/checkin')[0] if config['server']['url'].endswith('/checkin') else config['server']['url']
    url = f"{base_url}/checkin"
    hostname = get_hostname()
    
    logger.info(f"Starting connection attempts with hostname: {hostname}")
    logger.info(f"Server URL: {url}")
    logger.info(f"Max attempts: {max_attempts}, Delay: {delay_seconds} seconds")
    
    max_attempts = max_attempts or config['server'].get('max_retry_attempts', 10)
    delay_seconds = delay_seconds or config['server'].get('retry_delay_seconds', 60)
    version = config.get('version', '1.0.0')  
    for attempt in range(max_attempts):
        try:
            parsed = urlparse(base_url)
            host = parsed.hostname
            port = parsed.port or 3001
            ip, family = get_ip_address(host, port)
            new_url = f"{parsed.scheme}://{ip}:{port}/checkin"
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Sending request to {new_url}")
            client_time = datetime.now()
            logger.info(f"Request data: hostname={hostname}, time={client_time.isoformat()}")
            response = requests.post(new_url,
                                    json={"hostname": hostname, "client_time": client_time.isoformat(), "version": version},
                                    timeout=config['server']['timeout_seconds'])
            
            if response.status_code == 200:
                logger.info(f"Success: Server accepted check-in at {datetime.now()}")
                save_success_date()
                sys.exit(0)
            elif response.status_code == 208:
                logger.info(f"Server already checked in today at {datetime.now()}")
                save_success_date()
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
        time.sleep(config['application'].get('startup_delay_seconds', 0))
        
        last_date = get_last_success_date()
        today = datetime.now().strftime('%Y-%m-%d')
        if last_date == today:
            logger.info(f"Already checked in today at {datetime.now()}")
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