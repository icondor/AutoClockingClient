import win32api
import win32con
import win32event
import win32gui
import win32ts
import winerror
import os
import logging
import subprocess
import time
import sys
from win32gui import MSG  # Explicitly import MSG class

class PowerMonitor:
    def __init__(self):
        self.app_support = os.path.join(os.environ['APPDATA'], 'AttendanceTracker')
        os.makedirs(self.app_support, exist_ok=True)
        
        log_dir = os.path.join(self.app_support, 'Logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            filename=os.path.join(log_dir, 'power_monitor.log'),
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s'
        )
        
        self.last_event_time = 0
        self.min_event_interval = 5
        
    def launchApp(self):
        try:
            current_time = time.time()
            if current_time - self.last_event_time < self.min_event_interval:
                logging.info("Skipping launch due to recent event")
                return
            
            self.last_event_time = current_time
            
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            if not os.path.exists(app_path):
                logging.error(f"AttendanceTracker not found at: {app_path}")
                return
            
            process = subprocess.Popen(
                [app_path],
                stdout=open(os.path.join(self.app_support, 'attendance.log'), 'a'),
                stderr=open(os.path.join(self.app_support, 'attendance.error'), 'a'),
                cwd=self.app_support,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logging.info(f"Launched AttendanceTracker with PID {process.pid}")
        except subprocess.SubprocessError as e:
            logging.error(f"Subprocess error: {str(e)}")
        except PermissionError as e:
            logging.error(f"Permission denied: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        self.launchApp()

def WndProc(hWnd, msg, wParam, lParam):
    monitor = getattr(sys.modules[__name__], 'monitor', None)
    if not monitor:
        return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
    
    try:
        if msg == win32con.WM_POWERBROADCAST:
            if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                monitor.handleEvent("wake")
                return True
        elif msg == win32con.WM_WTSSESSION_CHANGE:
            if wParam == win32con.WTS_SESSION_UNLOCK:
                monitor.handleEvent("unlock")
                return True
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
    except AttributeError as e:
        logging.error(f"AttributeError in WndProc: {str(e)}")
    
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

def create_window():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = WndProc
    wc.lpszClassName = "PowerMonitorWindow"
    wc.hInstance = win32api.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)
    hWnd = win32gui.CreateWindow(class_atom, "PowerMonitor", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    return hWnd

def ensure_single_instance():
    mutex = win32event.CreateMutex(None, True, "Global\\AttendanceTracker_PowerMonitor")
    last_error = win32api.GetLastError()
    if last_error == winerror.ERROR_ALREADY_EXISTS:
        logging.info("Another instance of PowerMonitor is running—exiting")
        sys.exit(1)
    elif last_error != 0:
        logging.error(f"Mutex creation failed with error: {last_error}")
        sys.exit(1)
    return True

def run_message_loop(hWnd):
    try:
        win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION)
        msg = MSG()
        while win32gui.GetMessage(msg, 0, 0, 0) > 0:
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)
    finally:
        win32ts.WTSUnRegisterSessionNotification(hWnd)

if __name__ == '__main__':
    ensure_single_instance()
    
    hWnd = None
    try:
        sys.modules[__name__].monitor = PowerMonitor()
        logging.info("Starting PowerMonitor...")
        
        hWnd = create_window()
        sys.modules[__name__].monitor.handleEvent("startup")
        
        run_message_loop(hWnd)
    
    except Exception as e:
        logging.error(f"Error in main: {str(e)}")
    finally:
        if hWnd:
            try:
                win32gui.DestroyWindow(hWnd)
            except Exception as e:
                logging.error(f"Failed to destroy window: {str(e)}")