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

# Try to import win32ts, but don't fail if not available
try:
    import win32ts
    HAS_WIN32TS = True
except ImportError:
    HAS_WIN32TS = False
    logging.warning("win32ts module not available - session notifications will be disabled")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('power_monitor.log'),
        logging.StreamHandler()
    ]
)

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

def verify_win32_features():
    """Verify that all required Windows API features are available."""
    try:
        # Check for basic window message functions
        if not hasattr(win32gui, 'PeekMessage'):
            logging.error("win32gui.PeekMessage not available")
            return False
        if not hasattr(win32gui, 'TranslateMessage'):
            logging.error("win32gui.TranslateMessage not available")
            return False
        if not hasattr(win32gui, 'DispatchMessage'):
            logging.error("win32gui.DispatchMessage not available")
            return False
            
        # Check for window constants
        if not hasattr(win32con, 'WM_QUIT'):
            logging.error("win32con.WM_QUIT not available")
            return False
        if not hasattr(win32con, 'WM_POWERBROADCAST'):
            logging.error("win32con.WM_POWERBROADCAST not available")
            return False
        if not hasattr(win32con, 'PBT_APMRESUMEAUTOMATIC'):
            logging.error("win32con.PBT_APMRESUMEAUTOMATIC not available")
            return False
            
        logging.info("Basic Windows API features verified")
        return True
    except Exception as e:
        logging.error(f"Error verifying Windows API features: {e}")
        return False

def run_message_loop(hWnd):
    """Run the Windows message loop."""
    session_notifications_registered = False
    
    try:
        # Create a message structure using ctypes
        import ctypes
        from ctypes.wintypes import HWND, UINT, WPARAM, LPARAM, BOOL
        
        class MSG(ctypes.Structure):
            _fields_ = [
                ("hWnd", HWND),
                ("message", UINT),
                ("wParam", WPARAM),
                ("lParam", LPARAM),
                ("time", ctypes.c_ulong),
                ("pt_x", ctypes.c_long),
                ("pt_y", ctypes.c_long),
            ]
            
        msg = MSG()
        
        # Try to register for session notifications if available
        if HAS_WIN32TS:
            try:
                if win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION):
                    session_notifications_registered = True
                    logging.info("Successfully registered for session notifications")
            except Exception as e:
                logging.warning(f"Session notifications not available: {e}")
        else:
            logging.info("Session notifications not available (win32ts not imported)")
            
        # Main message loop using PeekMessage
        while True:
            try:
                if win32gui.PeekMessage(msg, 0, 0, 0, win32con.PM_REMOVE):
                    if msg.message == win32con.WM_QUIT:
                        logging.info("Received WM_QUIT, exiting message loop")
                        break
                        
                    try:
                        win32gui.TranslateMessage(msg)
                        win32gui.DispatchMessage(msg)
                    except Exception as e:
                        logging.error(f"Error processing message: {e}")
                        continue
                else:
                    # No messages, sleep a bit to prevent CPU hogging
                    time.sleep(0.1)
                    
            except Exception as e:
                logging.error(f"Error in message loop iteration: {e}")
                # Don't break, try to continue processing messages
                time.sleep(0.1)
                
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
    """Window procedure for handling Windows messages."""
    try:
        monitor = getattr(sys.modules[__name__], 'monitor', None)
        if not monitor:
            return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
            
        # Handle power events
        if msg == win32con.WM_POWERBROADCAST:
            if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                logging.info("Received power resume event")
                if monitor.handleEvent("wake"):
                    return True
                    
        # Handle session events if available
        elif HAS_WIN32TS and msg == win32con.WM_WTSSESSION_CHANGE:
            if wParam == win32con.WTS_SESSION_UNLOCK:
                logging.info("Received session unlock event")
                if monitor.handleEvent("unlock"):
                    return True
                    
        elif msg == win32con.WM_DESTROY:
            logging.info("Received WM_DESTROY")
            win32gui.PostQuitMessage(0)
            return 0
            
    except Exception as e:
        logging.error(f"Error in WndProc: {e}\n{traceback.format_exc()}")
        
    return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

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
        if last_error == win32con.ERROR_ALREADY_EXISTS:
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