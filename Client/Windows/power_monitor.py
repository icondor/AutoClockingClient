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
import traceback

# Early logging setup with more detailed error handling
try:
    log_dir = os.path.join(os.environ.get('APPDATA', ''), 'AttendanceTracker', 'Logs')
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(log_dir, 'power_monitor.log'),
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    logging.info("="*50)
    logging.info("PowerMonitor Starting")
    logging.info(f"Current Directory: {os.getcwd()}")
    logging.info(f"Script Location: {os.path.abspath(__file__)}")
    logging.info(f"Python Version: {sys.version}")
except Exception as e:
    # The fallback writes to current directory which might not be writable
    with open('power_monitor_startup.log', 'a') as f:
        f.write(f"Failed to setup logging: {str(e)}\n")
    raise  # We shouldn't raise here, should fallback to stderr

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
                logging.info("Directory contents:")
                try:
                    for item in os.listdir(self.app_support):
                        logging.info(f"  {item}")
                except Exception as e:
                    logging.error(f"Failed to list directory: {e}")
                return
            
            # Ensure log files are created with proper permissions
            log_path = os.path.join(self.app_support, 'attendance.log')
            error_path = os.path.join(self.app_support, 'attendance.error')
            
            stdout = open(log_path, 'a')
            stderr = open(error_path, 'a')
            
            process = subprocess.Popen(
                [app_path],
                stdout=stdout,
                stderr=stderr,
                cwd=self.app_support,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
            logging.info(f"Launched AttendanceTracker with PID {process.pid}")
            
            # Check immediate process status
            time.sleep(1)
            if process.poll() is not None:
                logging.error(f"Process terminated immediately with code: {process.poll()}")
                # Read any error output
                stderr.flush()
                with open(error_path, 'r') as f:
                    errors = f.read()
                    if errors:
                        logging.error(f"Process error output: {errors}")
            
        except subprocess.SubprocessError as e:
            logging.error(f"Subprocess error: {str(e)}\n{traceback.format_exc()}")
        except PermissionError as e:
            logging.error(f"Permission denied: {str(e)}\n{traceback.format_exc()}")
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        finally:
            try:
                stdout.close()
                stderr.close()
            except:
                pass

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        self.launchApp()

def WndProc(hWnd, msg, wParam, lParam):
    monitor = getattr(sys.modules[__name__], 'monitor', None)
    if not monitor:
        return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
    
    try:
        if not hasattr(win32con, 'WM_WTSSESSION_CHANGE'):
            logging.error("WM_WTSSESSION_CHANGE not available in win32con")
            return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)
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
    try:
        mutex = win32event.CreateMutex(None, True, "Global\\AttendanceTracker_PowerMonitor")
        last_error = win32api.GetLastError()
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            logging.info("Another instance of PowerMonitor is running—exiting")
            sys.exit(0)  # This should be 0 for expected conditions
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
        if not hasattr(win32gui, 'MSG'):
            logging.error("MSG class not available in win32gui—cannot run message loop")
            sys.exit(1)
        win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION)
        msg = win32gui.MSG()
        while win32gui.GetMessage(msg, 0, 0, 0) > 0:
            win32gui.TranslateMessage(msg)
            win32gui.DispatchMessage(msg)
    except Exception as e:
        logging.error(f"Error in message loop: {str(e)}")
        sys.exit(1)
    finally:
        try:
            win32ts.WTSUnRegisterSessionNotification(hWnd)
        except Exception as e:
            logging.error(f"Error unregistering session notification: {str(e)}")

if __name__ == '__main__':
    try:
        logging.info("PowerMonitor main entry point")
        ensure_single_instance()
        
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
        sys.modules[__name__].monitor.handleEvent("startup")
        
        logging.info("Entering message loop")
        run_message_loop(hWnd)
    
    except Exception as e:
        logging.error(f"Fatal error in PowerMonitor: {str(e)}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        if 'hWnd' in locals() and hWnd:
            try:
                win32gui.DestroyWindow(hWnd)
                logging.info("Window destroyed successfully")
            except Exception as e:
                logging.error(f"Failed to destroy window: {str(e)}")
        logging.info("PowerMonitor shutting down")