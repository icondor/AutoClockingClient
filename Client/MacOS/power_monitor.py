#!/usr/bin/env python3
import sys
import os
import logging
import signal
from datetime import datetime
import subprocess
import fcntl
import time

try:
    import objc
    from AppKit import NSWorkspace, NSObject, NSWorkspaceDidWakeNotification
    from Foundation import NSDistributedNotificationCenter  # For unlock
except ImportError as e:
    print(f"Failed to import required modules: {e}")
    print("Please ensure pyobjc is installed: pip install pyobjc-framework-Cocoa")
    sys.exit(1)

# Setup logging to file and console
log_dir = os.path.expanduser("~/Library/Application Support/AttendanceTracker")
os.makedirs(log_dir, exist_ok=True)

error_log = os.path.join(log_dir, 'error.log')
output_log = os.path.join(log_dir, 'output.log')
lock_file = os.path.join(log_dir, 'power_monitor.lock')

logging.basicConfig(
    filename=output_log,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logging.getLogger().addHandler(console_handler)

error_handler = logging.FileHandler(error_log)
error_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(error_handler)

class PowerMonitor(NSObject):
    def init(self):
        self = objc.super(PowerMonitor, self).init()
        if self is None:
            logging.error("Failed to initialize PowerMonitor")
            return None
            
        self.app_support = os.path.expanduser("~/Library/Application Support/AttendanceTracker")
        logging.info(f"Initializing monitor in GUI session: {os.environ.get('DISPLAY', 'No display')}")
        logging.info(f"User: {os.getenv('USER')}, Home: {os.getenv('HOME')}")
        logging.info(f"Using app support dir: {self.app_support}")
        workspace = NSWorkspace.sharedWorkspace()
        nc = workspace.notificationCenter()
        dnc = NSDistributedNotificationCenter.defaultCenter()
        logging.info("Setting up notification observers")
        
        nc.addObserver_selector_name_object_(
            self,
            'handleWake:',
            NSWorkspaceDidWakeNotification,
            None
        )
        logging.info(f"Added system wake observer: {NSWorkspaceDidWakeNotification}")
        
        dnc.addObserver_selector_name_object_(
            self,
            'handleUnlock:',
            'com.apple.screenIsUnlocked',
            None
        )
        logging.info("Added screen unlock observer: com.apple.screenIsUnlocked")
        
        dnc.addObserver_selector_name_object_(
            self,
            'handleLogin:',
            'com.apple.sessionDidBecomeActive',
            None
        )
        logging.info("Added login observer: com.apple.sessionDidBecomeActive")
        
        logging.info("====== Power Monitor Started - LOGIN EVENT ======")
        return self
        
    def handleWake_(self, notification):
        logging.info("====== SYSTEM WAKE EVENT DETECTED ======")
        logging.info(f"Notification details: {notification}")
        self.launchApp()

    def handleUnlock_(self, notification):
        logging.info("====== SCREEN UNLOCK EVENT DETECTED ======")
        logging.info(f"Notification details: {notification}")
        self.launchApp()

    def handleLogin_(self, notification):
        logging.info("====== LOGIN EVENT DETECTED ======")
        logging.info(f"Notification details: {notification}")
        self.launchApp()

    def launchApp(self):
        try:
            app_path = os.path.join(self.app_support, "AttendanceTracker.app/Contents/MacOS/AttendanceTracker")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            if os.path.exists(app_path):
                subprocess.Popen([app_path], 
                               cwd=self.app_support)
                logging.info("Launched AttendanceTracker in background")
            else:
                logging.error(f"AttendanceTracker not found at: {app_path}")
        except Exception as e:
            logging.error(f"Failed to launch AttendanceTracker: {str(e)}")

    def cleanup(self):
        logging.info("Cleaning up PowerMonitor")
        NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self)
        NSDistributedNotificationCenter.defaultCenter().removeObserver_(self)

def signal_handler(signum, frame, monitor, lock_fd):
    logging.info(f"Received signal {signum}, shutting down")
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
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        logging.info(f"Acquired lock, PID: {os.getpid()}")
        return lock_fd
    except IOError:
        time.sleep(0.1)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            logging.info(f"Acquired lock after retry, PID: {os.getpid()}")
            return lock_fd
        except IOError:
            logging.warning("Another instance of power_monitor is already running")
            lock_fd.close()
            sys.exit(0)

if __name__ == '__main__':
    logging.info("Power monitor script starting")
    
    lock_fd = ensure_single_instance()
    
    monitor = PowerMonitor.alloc().init()
    if monitor is None:
        logging.error("Monitor initialization failed, exiting")
        if lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()
        sys.exit(1)
    
    global_monitor = monitor
    logging.info("Monitor instance created, entering run loop")
    logging.info(f"Running with PID: {os.getpid()}")

    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, global_monitor, lock_fd))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, global_monitor, lock_fd))
    
    try:
        from PyObjCTools import AppHelper
        logging.info("Starting event loop")
        AppHelper.runConsoleEventLoop()
    except Exception as e:
        logging.error(f"Event loop crashed: {str(e)}", exc_info=True)
    finally:
        signal_handler(signal.SIGTERM, None, global_monitor, lock_fd)