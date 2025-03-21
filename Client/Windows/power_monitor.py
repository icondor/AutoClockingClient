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
import ctypes
from logging.handlers import RotatingFileHandler

import configparser  # Added for reading INI file

try:
    import win32ts
    HAS_WIN32TS = True
except ImportError:
    HAS_WIN32TS = False
    logging.warning("win32ts module not available - session notifications disabled")

# Define fallback constants
WM_WTSSESSION_CHANGE_FALLBACK = 0x02B1
WTS_SESSION_UNLOCK_FALLBACK = 0x8
WTS_SESSION_LOGON_FALLBACK = 0x5
WTS_SESSION_LOGOFF_FALLBACK = 0x6
WTS_SESSION_LOCK_FALLBACK = 0x7
PBT_APMRESUMEAUTOMATIC_FALLBACK = 0x12  # Added for wake from sleep
PBT_APMRESUMESUSPEND_FALLBACK = 0x4    # Added for user-triggered wake
PBT_APMSUSPEND_FALLBACK = 0x4          # Added for sleep (note: overlaps with RESUMESUSPEND, but typically 0x4)

# Configure logging with RotatingFileHandler from config file
app_support = os.path.join(os.environ.get('APPDATA', ''), 'AttendanceTracker')
logs_dir = os.path.join(app_support, 'logs')
os.makedirs(logs_dir, exist_ok=True)

power_monitor_log = os.path.join(logs_dir, 'powermonitor.log')

# Get the root logger and clear any existing handlers
logger = logging.getLogger()
for handler in logger.handlers:
    logger.removeHandler(handler)

# Load logging configuration from file
config_file = os.path.join(os.path.dirname(sys.executable), 'logging.conf')
config = configparser.ConfigParser()

# Default settings if config file is missing or invalid
log_level = 'DEBUG'
max_bytes = 10 * 1024 * 1024  # 10 MB

if os.path.exists(config_file):
    try:
        config.read(config_file)
        if 'logging' in config:
            log_level = config['logging'].get('level', 'DEBUG').upper()
            max_bytes = config['logging'].getint('max_size_mb', 10) * 1024 * 1024
    except Exception as e:
        logging.basicConfig(level=logging.ERROR)  # Temporary setup for error logging
        logging.error(f"Failed to read logging config from {config_file}: {e}")

# Set up RotatingFileHandler with settings from config or defaults
handler = RotatingFileHandler(power_monitor_log, mode='w', maxBytes=max_bytes, backupCount=0)
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
level = getattr(logging, log_level, logging.DEBUG)  # Fallback to DEBUG if invalid
logger.setLevel(level)
handler.setLevel(level)
logger.addHandler(handler)

# Import Windows modules
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

# Define MSG structure with ctypes
class MSG(ctypes.Structure):
    _fields_ = [
        ('hwnd', ctypes.c_void_p),
        ('message', ctypes.c_uint),
        ('wParam', ctypes.c_void_p),
        ('lParam', ctypes.c_void_p),
        ('time', ctypes.c_ulong),
        ('pt', ctypes.c_void_p),
    ]
logging.info("Defined MSG structure using ctypes since win32gui.MSG is unavailable")

# Access Windows API functions via ctypes
user32 = ctypes.windll.user32
GetMessageW = user32.GetMessageW
TranslateMessage = user32.TranslateMessage
DispatchMessageW = user32.DispatchMessageW

GetMessageW.argtypes = [ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
GetMessageW.restype = ctypes.c_int
TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
TranslateMessage.restype = ctypes.c_int
DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
DispatchMessageW.restype = ctypes.c_void_p

def is_process_running(process_name):
    try:
        result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {process_name}'], 
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return process_name.lower() in result.stdout.lower()
    except Exception as e:
        logging.error(f"Error checking process status: {e}")
        return False

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
            self.retry_reset_interval = 3600
            logging.info("PowerMonitor initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize PowerMonitor: {e}\n{traceback.format_exc()}")
            raise

    def _should_reset_retries(self):
        current_time = time.time()
        if current_time - self.last_event_time > self.retry_reset_interval:
            self.retry_count = 0
            logging.info("Reset retry counter due to time elapsed")
            return True
        return False

    def launchApp(self):
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
            logging.info(f"Launch attempt {self.retry_count} of {self.max_retries}")
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            if not os.path.exists(app_path):
                logging.error(f"AttendanceTracker not found at: {app_path}")
                return False
            process = subprocess.Popen(
                [app_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.app_support,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.SW_HIDE,
                startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=subprocess.SW_HIDE)
            )
            logging.info(f"Launched AttendanceTracker with PID {process.pid}")
            time.sleep(1)
            if process.poll() is not None:
                logging.error(f"Process terminated immediately with code: {process.poll()}")
                return False
            if not is_process_running("AttendanceTracker.exe"):
                logging.error("Process not found after starting")
                return False
            return True
        except Exception as e:
            logging.error(f"Error launching app: {e}\n{traceback.format_exc()}")
            return False

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        return self.launchApp()

def run_message_loop(hWnd):
    session_notifications_registered = False
    try:
        msg = MSG()
        logging.info("Starting message loop")
        if HAS_WIN32TS:
            logging.info(f"Attempting to register session notifications for hWnd={hWnd}")
            if win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION):
                session_notifications_registered = True
                logging.info("Successfully registered for session notifications")
            else:
                error = ctypes.get_last_error()
                logging.warning(f"Failed to register for session notifications, error: {error}")
        
        iteration = 0
        while True:
            iteration += 1
            logging.debug(f"Message loop iteration {iteration}")
            result = GetMessageW(ctypes.byref(msg), hWnd, 0, 0)
            if result == 0:
                logging.info("Received WM_QUIT, exiting message loop")
                break
            elif result == -1:
                error = ctypes.get_last_error()
                logging.error(f"Error in GetMessageW: {error}")
                break
            logging.info(f"Received message: hwnd={msg.hwnd}, message={msg.message}, wParam={msg.wParam}, lParam={msg.lParam}")
            TranslateMessage(ctypes.byref(msg))
            DispatchMessageW(ctypes.byref(msg))
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
            # Use fallbacks for power events
            pbt_apmresumeautomatic = getattr(win32con, 'PBT_APMRESUMEAUTOMATIC', PBT_APMRESUMEAUTOMATIC_FALLBACK)
            pbt_apmresumesuspend = getattr(win32con, 'PBT_APMRESUMESUSPEND', PBT_APMRESUMESUSPEND_FALLBACK)
            pbt_apmsuspend = getattr(win32con, 'PBT_APMSUSPEND', PBT_APMSUSPEND_FALLBACK)
            if wParam == pbt_apmresumeautomatic:
                logging.info("System resuming from suspend (automatic)")
                if monitor.handleEvent("wake"):
                    return True
            elif wParam == pbt_apmresumesuspend:
                logging.info("System resuming from suspend (user triggered)")
                if monitor.handleEvent("wake"):
                    return True
            elif wParam == pbt_apmsuspend:
                logging.info("System going to suspend")
                return True
            else:
                logging.info(f"Unhandled power event: wParam={wParam}")
        elif HAS_WIN32TS:
            session_change_msg = getattr(win32con, 'WM_WTSSESSION_CHANGE', WM_WTSSESSION_CHANGE_FALLBACK)
            if msg == session_change_msg:
                logging.info(f"Received session event: wParam={wParam}")
                # Use fallbacks for session events
                wts_session_unlock = getattr(win32con, 'WTS_SESSION_UNLOCK', WTS_SESSION_UNLOCK_FALLBACK)
                wts_session_logon = getattr(win32con, 'WTS_SESSION_LOGON', WTS_SESSION_LOGON_FALLBACK)
                wts_session_logoff = getattr(win32con, 'WTS_SESSION_LOGOFF', WTS_SESSION_LOGOFF_FALLBACK)
                wts_session_lock = getattr(win32con, 'WTS_SESSION_LOCK', WTS_SESSION_LOCK_FALLBACK)
                if wParam == wts_session_unlock:
                    logging.info("Session unlocked")
                    if monitor.handleEvent("unlock"):
                        return True
                elif wParam == wts_session_logon:
                    logging.info("User logged on")
                    if monitor.handleEvent("logon"):
                        return True
                elif wParam == wts_session_logoff:
                    logging.info("User logged off")
                    return True
                elif wParam == wts_session_lock:
                    logging.info("Session locked")
                    return True
                else:
                    logging.info(f"Unhandled session event: wParam={wParam}")
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
        logging.info(f"Window created with hWnd={hWnd}")
        win32gui.SendMessage(hWnd, win32con.WM_POWERBROADCAST, 
                           getattr(win32con, 'PBT_APMRESUMEAUTOMATIC', PBT_APMRESUMEAUTOMATIC_FALLBACK), 0)
        return hWnd
    except Exception as e:
        logging.error(f"Error in create_window: {e}\n{traceback.format_exc()}")
        return None

if __name__ == '__main__':
    try:
        logging.info("PowerMonitor main entry point")
        ensure_single_instance()
        if is_process_running("AttendanceTracker.exe"):
            subprocess.run(['taskkill', '/F', '/IM', 'AttendanceTracker.exe'], capture_output=True)
            time.sleep(1)
        sys.modules[__name__].monitor = PowerMonitor()
        logging.info("PowerMonitor instance created successfully")
        hWnd = create_window()
        if not hWnd:
            logging.error("Failed to create window")
            sys.exit(1)
        logging.info("Window created successfully")
        logging.info("Entering message loop")
        run_message_loop(hWnd)
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