import win32api
import win32con
import win32event
import win32gui
import winerror
import os
import logging
import subprocess
import time
import ctypes
from ctypes import wintypes
import sys

class PowerMonitor:
    def __init__(self):
        self.app_support = os.path.join(os.environ['APPDATA'], 'AttendanceTracker')
        os.makedirs(self.app_support, exist_ok=True)
        
        # Setup logging
        log_dir = os.path.join(self.app_support, 'Logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            filename=os.path.join(log_dir, 'power_monitor.log'),
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s'
        )
        
        # Initialize last event time to prevent duplicate events
        self.last_event_time = 0
        self.min_event_interval = 5  # minimum seconds between events
        
    def launchApp(self):
        try:
            # Prevent duplicate launches
            current_time = time.time()
            if current_time - self.last_event_time < self.min_event_interval:
                logging.info("Skipping launch due to recent event")
                return
            
            self.last_event_time = current_time
            
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            if os.path.exists(app_path):
                subprocess.Popen([app_path],
                               stdout=open(os.path.join(self.app_support, 'attendance.log'), 'a'),
                               stderr=open(os.path.join(self.app_support, 'attendance.error'), 'a'),
                               cwd=self.app_support)
                logging.info("Launched AttendanceTracker in background")
            else:
                logging.error(f"AttendanceTracker not found at: {app_path}")
        except Exception as e:
            logging.error(f"Failed to launch AttendanceTracker: {str(e)}")

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        self.launchApp()

def WndProc(hWnd, msg, wParam, lParam):
    if msg == win32con.WM_POWERBROADCAST:
        if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
            monitor.handleEvent("wake")
        return True
    elif msg == win32con.WM_WTSSESSION_CHANGE:
        if wParam == win32con.WTS_SESSION_UNLOCK:
            monitor.handleEvent("unlock")
        return True
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

def create_window():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = WndProc
    wc.lpszClassName = "PowerMonitorWindow"
    wc.hInstance = win32api.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)
    return win32gui.CreateWindow(class_atom,
        "PowerMonitor",
        0,
        0, 0, 0, 0,
        0,
        0,
        wc.hInstance,
        None)

def ensure_single_instance():
    mutex = win32event.CreateMutex(None, 1, "Global\\AttendanceTracker")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        return False
    return True

if __name__ == '__main__':
    if not ensure_single_instance():
        sys.exit(0)
        
    try:
        monitor = PowerMonitor()
        logging.info("Starting PowerMonitor...")
        
        # Register for session notifications
        hWnd = create_window()
        
        # Register for power notifications
        win32gui.WTSRegisterSessionNotification(hWnd, win32con.NOTIFY_FOR_THIS_SESSION)
        
        # Trigger initial check
        monitor.handleEvent("startup")
        
        # Message loop
        while True:
            win32gui.PumpWaitingMessages()
            time.sleep(0.1)
            
    except Exception as e:
        logging.error(f"Error in main loop: {str(e)}")
    finally:
        try:
            win32gui.WTSUnRegisterSessionNotification(hWnd)
        except:
            pass 