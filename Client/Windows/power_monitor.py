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

try:
    import win32ts
    HAS_WIN32TS = True
except ImportError:
    HAS_WIN32TS = False
    logging.warning("win32ts module not available - session notifications will be disabled")

WM_WTSSESSION_CHANGE_FALLBACK = 0x02B1

# Configure logging
app_support = os.path.join(os.environ.get('APPDATA', ''), 'AttendanceTracker')
logs_dir = os.path.join(app_support, 'logs')
os.makedirs(logs_dir, exist_ok=True)

power_monitor_log = os.path.join(logs_dir, 'power_monitor.log')
attendance_log = os.path.join(logs_dir, 'attendance.log')
attendance_error = os.path.join(logs_dir, 'attendance.error')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(power_monitor_log), logging.StreamHandler()]
)

# ... (rest of imports and module loading unchanged) ...

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
            logging.info(f"Launch attempt {self.retry_count} of {self.max_retries}")
            app_path = os.path.join(self.app_support, "AttendanceTracker.exe")
            logging.info(f"Attempting to launch AttendanceTracker from: {app_path}")
            if not os.path.exists(app_path):
                logging.error(f"AttendanceTracker not found at: {app_path}")
                return False
            stdout = open(attendance_log, 'a')
            stderr = open(attendance_error, 'a')
            process = subprocess.Popen(
                [app_path],
                stdout=stdout,
                stderr=stderr,
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
        finally:
            if stdout:
                stdout.close()
            if stderr:
                stderr.close()

    def handleEvent(self, event_type):
        logging.info(f"Handling event: {event_type}")
        return self.launchApp()

def run_message_loop(hWnd):
    session_notifications_registered = False
    last_power_state = None
    try:
        if HAS_WIN32TS:
            if win32ts.WTSRegisterSessionNotification(hWnd, win32ts.NOTIFY_FOR_THIS_SESSION):
                session_notifications_registered = True
                logging.info("Successfully registered for session notifications")
        
        msg_class = getattr(win32gui, 'MSG', None)
        if not msg_class:
            logging.warning("win32gui.MSG not available; using polling mode")
            monitor.handleEvent("startup")  # Launch on start
            while True:
                # Poll power state
                power_state = win32gui.SystemParametersInfo(win32con.SPI_GETPOWEROFFACTIVE, 0, None, 0)
                if last_power_state is not None and power_state != last_power_state:
                    if not power_state:
                        logging.info("System resumed from suspend (polling)")
                        monitor.handleEvent("wake")
                last_power_state = power_state
                time.sleep(5)  # Poll every 5s
                logging.debug("Polling for system events")
        else:
            msg = msg_class()
            while True:
                result = win32gui.GetMessage(msg, hWnd, 0, 0)
                if result == 0:
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

# ... (WndProc and other functions unchanged) ...

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
        run_message_loop(hWnd)  # Runs indefinitely or exits cleanly
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