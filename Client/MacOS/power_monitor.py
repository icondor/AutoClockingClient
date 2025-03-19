#!/usr/bin/env python3
import sys
import os
import logging
import signal
from datetime import datetime
import subprocess
import fcntl
import time
from logging.handlers import RotatingFileHandler
import configparser

try:
    import objc
    from AppKit import NSWorkspace, NSObject, NSWorkspaceDidWakeNotification
    from Foundation import NSDistributedNotificationCenter
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Please ensure pyobjc is installed: pip install pyobjc-framework-Cocoa")
    sys.exit(1)

# Setup paths
APP_SUPPORT = os.path.expanduser("~/Library/Application Support/AttendanceTracker")
LOG_DIR = os.path.join(APP_SUPPORT, 'Logs')
os.makedirs(LOG_DIR, exist_ok=True)
ATT_LOCK_FILE = os.path.join(APP_SUPPORT, 'attendance_tracker.lock')  # Lock file for AttendanceTracker

# Log file for power_monitor
log_file = os.path.join(LOG_DIR, 'outputpw.log')
lock_file = os.path.join(APP_SUPPORT, 'power_monitor.lock')

# Configure logging
logger = logging.getLogger('PowerMonitor')
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

config_file = os.path.join(APP_SUPPORT, 'logging.conf')
config = configparser.ConfigParser()
log_level = 'INFO'
max_bytes = 10 * 1024 * 1024

if os.path.exists(config_file):
    try:
        config.read(config_file)
        if 'logging' in config:
            log_level = config['logging'].get('level', 'INFO').upper()
            max_size_mb = config['logging'].getfloat('max_size_mb', 10.0)  # Handles 0.01 correctly
            max_bytes = int(max_size_mb * 1024 * 1024)  # Converts MB to bytes
            logger.info(f"Configured max log size: {max_size_mb} MB ({max_bytes} bytes)")
    except Exception as e:
        print(f"Failed to parse logging.conf: {e}", file=sys.stderr)

logger.setLevel(getattr(logging, log_level, logging.INFO))

handler = RotatingFileHandler(log_file, mode='a', maxBytes=max_bytes, backupCount=1)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
logger.addHandler(handler)

if os.environ.get('DEBUG'):
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(console_handler)

logger.info("Power monitor logging initialized")

class PowerMonitor(NSObject):
    def init(self):
        self = objc.super(PowerMonitor, self).init()
        if self is None:
            logger.error("Failed to initialize PowerMonitor")
            return None

        self.app_support = APP_SUPPORT
        logger.info(f"Initializing monitor in GUI session: {os.environ.get('DISPLAY', 'No display')}")
        logger.info(f"User: {os.getenv('USER')}, Home: {os.getenv('HOME')}")
        logger.info(f"Using app support dir: {self.app_support}")
        workspace = NSWorkspace.sharedWorkspace()
        nc = workspace.notificationCenter()
        dnc = NSDistributedNotificationCenter.defaultCenter()
        logger.info("Setting up notification observers")

        nc.addObserver_selector_name_object_(self, 'handleWake:', NSWorkspaceDidWakeNotification, None)
        logger.info(f"Added system wake observer: {NSWorkspaceDidWakeNotification}")
        dnc.addObserver_selector_name_object_(self, 'handleUnlock:', 'com.apple.screenIsUnlocked', None)
        logger.info("Added screen unlock observer: com.apple.screenIsUnlocked")
        dnc.addObserver_selector_name_object_(self, 'handleLogin:', 'com.apple.sessionDidBecomeActive', None)
        logger.info("Added login observer: com.apple.sessionDidBecomeActive")

        # Launch AttendanceTracker immediately on startup
        logger.info("Launching AttendanceTracker on startup")
        self.launchApp()

        logger.info("====== Power Monitor Started ======")
        return self

    def handleWake_(self, notification):
        logger.info("====== SYSTEM WAKE EVENT DETECTED ======")
        logger.debug(f"Notification details: {notification}")
        self.launchApp()

    def handleUnlock_(self, notification):
        logger.info("====== SCREEN UNLOCK EVENT DETECTED ======")
        logger.debug(f"Notification details: {notification}")
        self.launchApp()

    def handleLogin_(self, notification):
        logger.info("====== LOGIN EVENT DETECTED ======")
        logger.debug(f"Notification details: {notification}")
        self.launchApp()

    def launchApp(self):
        try:
            app_path = os.path.join(self.app_support, "AttendanceTracker.app/Contents/MacOS/AttendanceTracker")
            logger.info(f"Checking if AttendanceTracker exists at: {app_path}")
            if os.path.exists(app_path):
                logger.info(f"File permissions: {oct(os.stat(app_path).st_mode & 0o777)}")
                # Check if AttendanceTracker is already running via lock file with retries
                for attempt in range(3):  # Retry 3 times to avoid timing issues
                    if os.path.exists(ATT_LOCK_FILE):
                        logger.info(f"Lock file {ATT_LOCK_FILE} exists, checking if process is running (attempt {attempt + 1}/3)")
                        try:
                            with open(ATT_LOCK_FILE, 'r') as f:
                                pid = int(f.read().strip())
                            os.kill(pid, 0)  # Test if PID is alive
                            logger.info(f"AttendanceTracker is already running with PID: {pid}, skipping launch")
                            return
                        except (OSError, ValueError):
                            logger.info(f"Lock file {ATT_LOCK_FILE} is stale, removing it")
                            os.remove(ATT_LOCK_FILE)
                    else:
                        logger.info(f"No lock file found at {ATT_LOCK_FILE} (attempt {attempt + 1}/3), waiting briefly")
                    time.sleep(0.5)  # Wait 0.5 seconds before retrying
                # Launch new instance
                logger.info(f"Attempting to launch AttendanceTracker from: {app_path}")
                env = os.environ.copy()
                env['HOME'] = os.path.expanduser("~")  # Only set necessary environment variables
                # output_file = os.path.join(LOG_DIR, f"attendance_tracker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
                # process = subprocess.Popen(
                #     ['/bin/bash', '-c', f'"{app_path}" > "{output_file}" 2>&1'],
                #     cwd=self.app_support,
                #     env=env
                # )

                process = subprocess.Popen(
                    ['/bin/bash', '-c', f'"{app_path}" > /dev/null 2>&1'],
                    cwd=self.app_support,
                    env=env
                )
                logger.info(f"Launched AttendanceTracker with PID: {process.pid}")
            else:
                logger.error(f"AttendanceTracker not found at: {app_path}")
        except Exception as e:
            logger.error(f"Failed to launch AttendanceTracker: {str(e)}", exc_info=True)

    def cleanup(self):
        logger.info("Cleaning up PowerMonitor")
        if os.path.exists(ATT_LOCK_FILE):
            logger.info("Removing attendance_tracker.lock on power_monitor shutdown")
            try:
                os.remove(ATT_LOCK_FILE)
            except OSError as e:
                logger.error(f"Failed to remove lock file: {e}")
        NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self)
        NSDistributedNotificationCenter.defaultCenter().removeObserver_(self)

def signal_handler(signum, frame, monitor, lock_fd):
    logger.info(f"Received signal {signum}, shutting down")
    monitor.cleanup()
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        try:
            os.remove(lock_file)
        except OSError:
            pass
    sys.exit(0)

def ensure_single_instance():
    lock_fd = open(lock_file, 'w')
    try:
        # Ensure the lock file is writable
        os.chmod(lock_file, 0o666)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        logger.info(f"Acquired lock, PID: {os.getpid()}")
        return lock_fd
    except IOError as e:
        logger.warning(f"Failed to acquire lock on first attempt: {e}")
        # Retry with exponential backoff
        for attempt in range(3):
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_fd.write(str(os.getpid()))
                lock_fd.flush()
                logger.info(f"Acquired lock after retry {attempt + 1}, PID: {os.getpid()}")
                return lock_fd
            except IOError as e:
                logger.warning(f"Retry {attempt + 1} failed: {e}")
        # If all retries fail, check the lock file's PID
        try:
            with open(lock_file, 'r') as f:
                existing_pid = int(f.read().strip())
            os.kill(existing_pid, 0)  # Test if PID is alive
            logger.info(f"Confirmed existing power_monitor with PID: {existing_pid}")
        except (OSError, ValueError) as e:
            logger.error(f"Stale lock file detected, removing: {e}")
            os.remove(lock_file)
            # Retry one last time
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_fd.write(str(os.getpid()))
                lock_fd.flush()
                logger.info(f"Acquired lock after removing stale lock, PID: {os.getpid()}")
                return lock_fd
            except IOError:
                logger.error("Failed to acquire lock after removing stale lock")
        lock_fd.close()
        logger.warning("Another instance of power_monitor is already running, exiting")
        sys.exit(0)

if __name__ == "__main__":
    logger.info("Power monitor script starting")
    lock_fd = ensure_single_instance()
    monitor = PowerMonitor.alloc().init()
    if monitor is None:
        logger.error("Monitor initialization failed, exiting")
        if lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        sys.exit(1)
    global_monitor = monitor
    logger.info("Monitor instance created, entering run loop")
    logger.info(f"Running with PID: {os.getpid()}")
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, global_monitor, lock_fd))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, global_monitor, lock_fd))
    def heartbeat():
        while True:
            logger.info("Heartbeat: PowerMonitor is still running")
            time.sleep(60)
    import threading
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        from PyObjCTools import AppHelper
        logger.info("Starting event loop")
        AppHelper.runConsoleEventLoop()
    except Exception as e:
        logger.error(f"Event loop crashed: {str(e)}", exc_info=True)
    finally:
        signal_handler(signal.SIGTERM, None, global_monitor, lock_fd)