import os
import sys
import logging
import subprocess
import time
import traceback
from winerror import ERROR_ALREADY_EXISTS  # Import directly from winerror

# Early logging setup with proper fallback
try:
    log_dir = os.path.join(os.environ.get('APPDATA', ''), 'AttendanceTracker', 'Logs')
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_dir, 'power_monitor.log'),
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
except Exception as e:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    logging.error(f"Failed to setup file logging: {e}. Falling back to stderr.")

logging.info("="*50)
logging.info("PowerMonitor Starting")
logging.info(f"Current Directory: {os.getcwd()}")
logging.info(f"Script Location: {os.path.abspath(__file__)}")
logging.info(f"Python Version: {sys.version}")

# Import Windows modules with proper error handling
required_modules = {
    'win32api': None,
    'win32con': None,
    'win32event': None,
    'win32gui': None
}

# First, import the core modules we absolutely need
for module_name in required_modules:
    try:
        module = __import__(module_name)
        required_modules[module_name] = module
        logging.info(f"Successfully imported {module_name}")
    except ImportError as e:
        logging.error(f"Failed to import {module_name}: {e}")
        sys.exit(1)

# Now we can safely use these modules
win32api = required_modules['win32api']
win32con = required_modules['win32con']
win32event = required_modules['win32event']
win32gui = required_modules['win32gui']

# Try to import optional modules
try:
    import win32process
    HAS_WIN32PROCESS = True
    logging.info("Successfully imported win32process")
except ImportError:
    HAS_WIN32PROCESS = False
    logging.warning("win32process module not available - using alternative process check")

try:
    import win32ts
    HAS_WIN32TS = True
    logging.info("Successfully imported win32ts")
except ImportError:
    HAS_WIN32TS = False
    logging.warning("win32ts module not available - session unlock detection disabled")

def is_process_running(process_name):
    """Check if a process is already running."""
    try:
        # Use tasklist to find process
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
            logging.info("PowerMonitor initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize PowerMonitor: {e}\n{traceback.format_exc()}")
            raise
        
    def launchApp(self):
        stdout = stderr = None
        try:
            current_time = time.time()
            if current_time - self.last_event_time < self.min_event_interval:
                logging.info("Skipping launch due to recent event")
                return True

            # Check if AttendanceTracker is already running
            if is_process_running("AttendanceTracker.exe"):
                logging.info("AttendanceTracker is already running")
                return True
            
            self.last_event_time = current_time
            
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            
            if not os.path.exists(app_path):
                logging.error(f"AttendanceTracker not found at: {app_path}")
                return False
            
            # Ensure log files are created with proper permissions
            log_path = os.path.join(self.app_support, 'attendance.log')
            error_path = os.path.join(self.app_support, 'attendance.error')
            
            stdout = open(log_path, 'a')
            stderr = open(error_path, 'a')
            
            # Use all available flags to hide the window
            creation_flags = (
                subprocess.CREATE_NO_WINDOW |      # Don't create a console window
                subprocess.DETACHED_PROCESS |      # Detach from parent process
                subprocess.SW_HIDE                 # Hide any window that might appear
            )
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE  # Hide the window
            
            process = subprocess.Popen(
                [app_path],
                stdout=stdout,
                stderr=stderr,
                cwd=self.app_support,
                creationflags=creation_flags,
                startupinfo=startupinfo
            )
            logging.info(f"Launched AttendanceTracker with PID {process.pid}")
            
            # Verify process started successfully
            time.sleep(1)
            if process.poll() is not None:
                exit_code = process.poll()
                logging.error(f"Process terminated immediately with code: {exit_code}")
                stderr.flush()
                with open(error_path, 'r') as f:
                    errors = f.read()
                    if errors:
                        logging.error(f"Process error output: {errors}")
                return False
                
            # Double-check the process is running
            if not is_process_running("AttendanceTracker.exe"):
                logging.error("Process not found after starting")
                return False
                
            # Check attendance.log and attendance.error for startup issues
            time.sleep(2)  # Give it time to write logs
            try:
                with open(log_path, 'r') as f:
                    log_content = f.read()
                    if log_content:
                        logging.info(f"AttendanceTracker log: {log_content}")
                with open(error_path, 'r') as f:
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
                try:
                    stdout.close()
                except:
                    pass
            if stderr:
                try:
                    stderr.close()
                except:
                    pass

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        return self.launchApp()

def WndProc(hWnd, msg, wParam, lParam):
    monitor = getattr(sys.modules[__name__], 'monitor', None)
    if not monitor:
        return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
    
    try:
        if msg == win32con.WM_POWERBROADCAST:
            if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                if monitor.handleEvent("wake"):
                    return True
        # Only handle session change if win32ts is available
        elif HAS_WIN32TS and hasattr(win32con, 'WM_WTSSESSION_CHANGE'):
            if msg == win32con.WM_WTSSESSION_CHANGE:
                if wParam == win32con.WTS_SESSION_UNLOCK:
                    if monitor.handleEvent("unlock"):
                        return True
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
    except Exception as e:
        logging.error(f"Error in WndProc: {e}\n{traceback.format_exc()}")
    
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

def verify_win32_features():
    """Verify that all required Windows API features are available."""
    required_features = {
        'win32gui.MSG': hasattr(win32gui, 'MSG'),
        'win32con.WM_POWERBROADCAST': hasattr(win32con, 'WM_POWERBROADCAST'),
        'win32con.PBT_APMRESUMEAUTOMATIC': hasattr(win32con, 'PBT_APMRESUMEAUTOMATIC')
    }
    
    # Session notification features are optional
    if HAS_WIN32TS:
        required_features.update({
            'win32con.WM_WTSSESSION_CHANGE': hasattr(win32con, 'WM_WTSSESSION_CHANGE'),
            'win32con.WTS_SESSION_UNLOCK': hasattr(win32con, 'WTS_SESSION_UNLOCK')
        })
    
    missing_features = [name for name, available in required_features.items() if not available]
    if missing_features:
        logging.error(f"Missing required Windows API features: {', '.join(missing_features)}")
        return False
        
    logging.info("All required Windows API features are available")
    if not HAS_WIN32TS:
        logging.warning("Session unlock detection will be disabled")
    return True

def create_window():
    try:
        # Initialize window class
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = WndProc
        wc.lpszClassName = "PowerMonitorWindow"
        wc.hInstance = win32api.GetModuleHandle(None)
        
        # Register class
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception as e:
            logging.error(f"Failed to register window class: {e}")
            return None
            
        # Create window
        try:
            hWnd = win32gui.CreateWindow(
                class_atom,
                "PowerMonitor",
                0, 0, 0, 0, 0,  # Style, X, Y, W, H
                0, 0,  # Parent, Menu
                wc.hInstance,
                None
            )
            if not hWnd:
                logging.error("CreateWindow returned NULL")
                return None
            return hWnd
        except Exception as e:
            logging.error(f"Failed to create window: {e}")
            return None
            
    except Exception as e:
        logging.error(f"Error in create_window: {e}\n{traceback.format_exc()}")
        return None

def ensure_single_instance():
    try:
        mutex = win32event.CreateMutex(None, True, "Global\\AttendanceTracker_PowerMonitor")
        last_error = win32api.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:  # Use the imported constant directly
            logging.info("Another instance of PowerMonitor is running—exiting normally")
            sys.exit(0)
        elif last_error != 0:
            logging.error(f"Mutex creation failed with error: {last_error}")
            sys.exit(1)
        logging.info("Successfully created mutex")
        return True
    except Exception as e:
        logging.error(f"Failed to create/check mutex: {e}\n{traceback.format_exc()}")
        sys.exit(1)

def run_message_loop(hWnd):
    try:
        # Verify Windows API features before starting
        if not verify_win32_features():
            logging.error("Required Windows API features not available")
            return False
            
        # Register for session notifications only if available
        session_notifications_registered = False
        if HAS_WIN32TS:
            try:
                result = win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION)
                if result:
                    session_notifications_registered = True
                    logging.info("Successfully registered for session notifications")
                else:
                    logging.warning("Failed to register for session notifications - continuing without")
            except Exception as e:
                logging.warning(f"Could not register for session notifications: {e}")
        
        # Message loop
        msg = win32gui.MSG()
        while win32gui.GetMessage(msg, 0, 0, 0) > 0:
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
            except Exception as e:
                logging.warning(f"Error unregistering session notification: {e}")

if __name__ == '__main__':
    try:
        logging.info("PowerMonitor main entry point")
        ensure_single_instance()
        
        # Kill any existing AttendanceTracker instances
        if is_process_running("AttendanceTracker.exe"):
            subprocess.run(['taskkill', '/F', '/IM', 'AttendanceTracker.exe'], 
                         capture_output=True)
            time.sleep(1)
        
        logging.info("Creating PowerMonitor instance")
        sys.modules[__name__].monitor = PowerMonitor()
        logging.info("PowerMonitor instance created successfully")
        
        logging.info("Creating window")
        hWnd = create_window()
        if not hWnd:
            logging.error("Failed to create window")
            sys.exit(1)
        logging.info("Window created successfully")
        
        logging.info("Handling startup event")
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