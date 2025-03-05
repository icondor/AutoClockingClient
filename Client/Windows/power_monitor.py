import os
import sys
import logging
import subprocess
import time
import traceback
import win32gui
import win32api
import win32con
import win32event
import winerror

# Try to import win32ts, but don't fail if not available
try:
    import win32ts
    HAS_WIN32TS = True
except ImportError:
    HAS_WIN32TS = False
    logging.warning("win32ts module not available - session notifications will be disabled")

# Fallback constant for WM_WTSSESSION_CHANGE (Windows API value: 0x02B1)
WM_WTSSESSION_CHANGE_FALLBACK = 0x02B1

# Configure logging
app_support = os.path.join(os.environ.get('APPDATA', ''), 'AttendanceTracker')
logs_dir = os.path.join(app_support, 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Define log file paths
power_monitor_log = os.path.join(logs_dir, 'power_monitor.log')
attendance_log = os.path.join(logs_dir, 'attendance.log')
attendance_error = os.path.join(logs_dir, 'attendance.error')
install_log = os.path.join(logs_dir, 'install.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(power_monitor_log),
        logging.StreamHandler()
    ]
)

logging.info("="*50)
logging.info("PowerMonitor Starting")
logging.info(f"Current Directory: {os.getcwd()}")
logging.info(f"Script Location: {os.path.abspath(__file__)}")
logging.info(f"Logs Directory: {logs_dir}")
logging.info(f"Python Version: {sys.version}")

# Import Windows modules with proper error handling
required_modules = {
    'win32api': None,
    'win32con': None,
    'win32event': None,
    'win32gui': None
}

for module_name in required_modules:
    try:
        module = __import__(module_name)
        required_modules[module_name] = module
        logging.info(f"Successfully imported {module_name}")
    except ImportError as e:
        logging.error(f"Failed to import {module_name}: {e}")
        sys.exit(1)

win32api = required_modules['win32api']
win32con = required_modules['win32con']
win32event = required_modules['win32event']
win32gui = required_modules['win32gui']

try:
    import win32process
    HAS_WIN32PROCESS = True
    logging.info("Successfully imported win32process")
except ImportError:
    HAS_WIN32PROCESS = False
    logging.warning("win32process module not available - using alternative process check")

def is_process_running(process_name):
    """Check if a process is already running."""
    try:
        result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {process_name}'], 
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return process_name.lower() in result.stdout.lower()
    except Exception as e:
        logging.error(f"Error checking process status: {e}")
        return False

class PowerMonitor:
    def __init__(self):
        try:
            self.app_support = os.path.join(os.environ['APPDATA'], 'AttendanceTracker')
            logging.info(f"Initializing PowerMonitor. App support dir: {self.app_support}")
            os.makedirs(self.app_support, exist_ok=True)
            
            self.last_event_time = 0
            self.min_event_interval = 5
            self.max_retries = 10
            self.retry_count = 0
            self.last_retry_time = 0
            self.retry_reset_interval = 3600
            logging.info("PowerMonitor initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize PowerMonitor: {e}\n{traceback.format_exc()}")
            raise
        
    def _should_reset_retries(self):
        current_time = time.time()
        if current_time - self.last_retry_time > self.retry_reset_interval:
            self.retry_count = 0
            self.last_retry_time = current_time
            logging.info("Reset retry counter due to time elapsed")
            return True
        return False
        
    def launchApp(self):
        stdout = stderr = None
        try:
            current_time = time.time()
            self._should_reset_retries()
            if self.retry_count >= self.max_retries:
                logging.error(f"Maximum retry attempts ({self.max_retries}) reached.")
                return False
                
            if current_time - self.last_event_time < self.min_event_interval:
                logging.info("Skipping launch due to recent event")
                return True

            if is_process_running("AttendanceTracker.exe"):
                logging.info("AttendanceTracker is already running")
                self.retry_count = 0
                return True
            
            self.last_event_time = current_time
            self.retry_count += 1
            self.last_retry_time = current_time
            
            logging.info(f"Launch attempt {self.retry_count} of {self.max_retries}")
            
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            
            if not os.path.exists(app_path):
                logging.error(f"AttendanceTracker not found at: {app_path}")
                return False
            
            stdout = open(attendance_log, 'a')
            stderr = open(attendance_error, 'a')
            
            creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.SW_HIDE
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            
            process = subprocess.Popen(
                [app_path],
                stdout=stdout,
                stderr=stderr,
                cwd=self.app_support,
                creationflags=creation_flags,
                startupinfo=startupinfo
            )
            logging.info(f"Launched AttendanceTracker with PID {process.pid}")
            
            time.sleep(1)
            if process.poll() is not None:
                exit_code = process.poll()
                logging.error(f"Process terminated immediately with code: {exit_code}")
                return False
                
            if not is_process_running("AttendanceTracker.exe"):
                logging.error("Process not found after starting")
                return False
                
            time.sleep(2)
            try:
                with open(attendance_log, 'r') as f:
                    log_content = f.read()
                    if log_content:
                        logging.info(f"AttendanceTracker log: {log_content}")
                with open(attendance_error, 'r') as f:
                    error_content = f.read()
                    if error_content:
                        logging.error(f"AttendanceTracker errors: {error_content}")
            except Exception as e:
                logging.error(f"Failed to read AttendanceTracker logs: {e}")
                
            return True
            
        except Exception as e:
            logging.error(f"Error launching app: {e}\n{traceback.format_exc()}")
            return False
        finally:
            if stdout:
                stdout.close()
            if stderr:
                stderr.close()

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        return self.launchApp()

def verify_win32_features():
    try:
        if not hasattr(win32gui, 'PeekMessage') or not hasattr(win32gui, 'TranslateMessage') or not hasattr(win32gui, 'DispatchMessage'):
            logging.error("Required win32gui message functions not available")
            return False
        if not hasattr(win32con, 'WM_QUIT') or not hasattr(win32con, 'WM_POWERBROADCAST') or not hasattr(win32con, 'PBT_APMRESUMEAUTOMATIC'):
            logging.error("Required win32con constants not available")
            return False
        logging.info("Basic Windows API features verified")
        return True
    except Exception as e:
        logging.error(f"Error verifying Windows API features: {e}")
        return False

def run_message_loop(hWnd):
    session_notifications_registered = False
    try:
        if HAS_WIN32TS:
            try:
                if win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION):
                    session_notifications_registered = True
                    logging.info("Successfully registered for session notifications")
            except Exception as e:
                logging.warning(f"Session notifications not available: {e}")
        
        # Use MSG structure with fallback
        msg_class = getattr(win32gui, 'MSG', None)
        if not msg_class:
            logging.error("win32gui.MSG not available; message loop disabled")
            monitor.handleEvent("startup")  # Run startup event as fallback
            return False
        msg = msg_class()
        
        while True:
            result = win32gui.GetMessage(msg, hWnd, 0, 0)
            if result == 0:  # WM_QUIT
                logging.info("Received WM_QUIT, exiting message loop")
                break
            elif result == -1:
                logging.error("Error in GetMessage")
                break
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)
        return True
    except Exception as e:
        logging.error(f"Error in message loop: {e}\n{traceback.format_exc()}")
        return False
    finally:
        if session_notifications_registered:
            try:
                win32ts.WTSUnRegisterSessionNotification(hWnd)
                logging.info("Unregistered session notifications")
            except Exception as e:
                logging.warning(f"Failed to unregister session notifications: {e}")

def WndProc(hWnd, msg, wParam, lParam):
    try:
        monitor = getattr(sys.modules[__name__], 'monitor', None)
        if not monitor:
            return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
            
        if msg == win32con.WM_POWERBROADCAST:
            logging.info(f"Received power event: wParam={wParam}")
            if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                logging.info("System resuming from suspend")
                if monitor.handleEvent("wake"):
                    return True
            elif wParam == win32con.PBT_APMRESUMESUSPEND:
                logging.info("System resuming from suspend (user triggered)")
                if monitor.handleEvent("wake"):
                    return True
            elif wParam == win32con.PBT_APMSUSPEND:
                logging.info("System going to suspend")
                return True
                    
        elif HAS_WIN32TS:
            # Use fallback if WM_WTSSESSION_CHANGE is missing
            session_change_msg = getattr(win32con, 'WM_WTSSESSION_CHANGE', WM_WTSSESSION_CHANGE_FALLBACK)
            if msg == session_change_msg:
                logging.info(f"Received session event: wParam={wParam}")
                if wParam == win32con.WTS_SESSION_UNLOCK:
                    logging.info("Session unlocked")
                    if monitor.handleEvent("unlock"):
                        return True
                elif wParam == win32con.WTS_SESSION_LOGON:
                    logging.info("User logged on")
                    if monitor.handleEvent("logon"):
                        return True
                elif wParam == win32con.WTS_SESSION_LOGOFF:
                    logging.info("User logged off")
                    return True
                elif wParam == win32con.WTS_SESSION_LOCK:
                    logging.info("Session locked")
                    return True
                    
        elif msg == win32con.WM_QUERYENDSESSION:
            logging.info("System shutdown/restart/logoff requested")
            return True
            
        elif msg == win32con.WM_ENDSESSION:
            logging.info("System session is ending")
            if wParam:
                logging.info("Session is actually ending")
                win32gui.PostQuitMessage(0)
            return 0
            
        elif msg == win32con.WM_DESTROY:
            logging.info("Received WM_DESTROY")
            win32gui.PostQuitMessage(0)
            return 0
            
    except Exception as e:
        logging.error(f"Error in WndProc: {e}\n{traceback.format_exc()}")
        
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

def create_window():
    try:
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = WndProc
        wc.lpszClassName = "PowerMonitorWindow"
        wc.hInstance = win32api.GetModuleHandle(None)
        wc.style = win32con.CS_GLOBALCLASS
        
        class_atom = win32gui.RegisterClass(wc)
        
        style = win32con.WS_OVERLAPPED
        hWnd = win32gui.CreateWindow(
            class_atom,
            "PowerMonitor",
            style,
            0, 0, 0, 0,
            0, 0,
            wc.hInstance,
            None
        )
        if not hWnd:
            logging.error("CreateWindow returned NULL")
            return None
            
        win32gui.SendMessage(hWnd, win32con.WM_POWERBROADCAST, 
                           win32con.PBT_APMRESUMEAUTOMATIC, 0)
        return hWnd
    except Exception as e:
        logging.error(f"Error in create_window: {e}\n{traceback.format_exc()}")
        return None

def ensure_single_instance():
    try:
        mutex = win32event.CreateMutex(None, True, "Global\\AttendanceTracker_PowerMonitor")
        last_error = win32api.GetLastError()
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            logging.info("Another instance of PowerMonitor is running—exiting")
            sys.exit(0)
        elif last_error != 0:
            logging.error(f"Mutex creation failed with error: {last_error}")
            sys.exit(1)
        logging.info("Successfully created mutex")
        return True
    except Exception as e:
        logging.error(f"Failed to create/check mutex: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        logging.info("PowerMonitor main entry point")
        ensure_single_instance()
        
        if is_process_running("AttendanceTracker.exe"):
            subprocess.run(['taskkill', '/F', '/IM', 'AttendanceTracker.exe'], 
                         capture_output=True)
            time.sleep(1)
        
        sys.modules[__name__].monitor = PowerMonitor()
        logging.info("PowerMonitor instance created successfully")
        
        hWnd = create_window()
        if not hWnd:
            logging.error("Failed to create window")
            sys.exit(1)
        logging.info("Window created successfully")
        
        if not sys.modules[__name__].monitor.handleEvent("startup"):
            logging.error("Failed to handle startup event")
            sys.exit(1)
        
        logging.info("Entering message loop")
        if not run_message_loop(hWnd):
            logging.error("Message loop failed")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Fatal error in PowerMonitor: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        if 'hWnd' in locals() and hWnd:
            try:
                win32gui.DestroyWindow(hWnd)
                logging.info("Window destroyed successfully")
            except Exception as e:
                logging.error(f"Failed to destroy window: {e}")
        logging.info("PowerMonitor shutting down")