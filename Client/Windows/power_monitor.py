import win32api
import win32con
import win32event
import win32service
import win32serviceutil
import servicemanager
import socket
import sys
import os
import logging
import subprocess
from pathlib import Path
import win32com.client
import pythoncom

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
        
    def launchApp(self):
        try:
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

def WaitForEvent():
    pythoncom.CoInitialize()
    wmi = win32com.client.GetObject("winmgmts://./root/cimv2")
    
    # Create event queries
    login_query = "SELECT * FROM Win32_ProcessStartTrace WHERE ProcessName='explorer.exe'"
    power_query = "SELECT * FROM Win32_PowerManagementEvent"
    
    login_watcher = wmi.ExecNotificationQuery(login_query)
    power_watcher = wmi.ExecNotificationQuery(power_query)
    
    monitor = PowerMonitor()
    
    while True:
        try:
            # Wait for either login or power events
            login_event = login_watcher.NextEvent(1000)  # 1 second timeout
            monitor.handleEvent("login")
        except:
            pass
            
        try:
            power_event = power_watcher.NextEvent(1000)
            if power_event.EventType in [7, 8]:  # Resume from sleep/hibernate
                monitor.handleEvent("wake")
            elif power_event.EventType == 4:  # Unlock
                monitor.handleEvent("unlock")
        except:
            pass

if __name__ == '__main__':
    try:
        WaitForEvent()
    except KeyboardInterrupt:
        pass 