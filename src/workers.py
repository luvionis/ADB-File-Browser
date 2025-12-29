import subprocess
import logging
import os
import zipfile
import tempfile
import re
import time
from PyQt6.QtCore import QThread, pyqtSignal

class AdbTransferWorker(QThread):
    # active_file, progress_percent, speed_str, eta_str
    progress_update = pyqtSignal(str, int, str, str)
    finished_transfer = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, command, device=None, parent=None):
        super().__init__(parent)
        self.command = command
        self.device = device
        self.is_running = True

    def run(self):
        try:
            cmd = self.command
            if self.device and self.device != "No Device":
                serial = self.device.split()[0]
                if cmd[0] == "adb":
                    cmd = ["adb", "-s", serial] + cmd[1:]
            
            # Ensure -p is present for push/pull commands for progress
            if "push" in cmd or "pull" in cmd:
                 pass
                 # Actually, it's safer to always insert -p after push/pull if not present
                 # But we need to find index.
            
            # Simple injection:
            new_cmd = []
            for part in cmd:
                new_cmd.append(part)
                if part in ["push", "pull"] and "-p" not in cmd:
                    new_cmd.append("-p")
            cmd = new_cmd

            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=True,
                bufsize=1
            )
            
            start_time = time.time()
            
            # Instead of simple 'for line in process.stdout', we read chunks to catch \r
            buffer = ""
            while True:
                char = process.stdout.read(1)
                if not char and process.poll() is not None:
                    break
                
                if not self.is_running:
                    process.terminate()
                    break
                
                if char in ['\r', '\n']:
                    if buffer:
                        line = buffer.strip()
                        # Parse logic
                        match = re.search(r'\[\s*(\d+)%\]', line)
                        if match:
                            percent = int(match.group(1))
                            speed_match = re.search(r'(\d+\.?\d+\s*[KMG]?B/s)', line)
                            speed = speed_match.group(1) if speed_match else ""
                            self.progress_update.emit("Transferring...", percent, speed, "")
                        
                        logging.debug(f"ADB Transfer: {line}")
                        buffer = ""
                else:
                    buffer += char

            process.wait()
            if process.returncode == 0:
                self.finished_transfer.emit()
            else:
                self.error_occurred.emit(f"Transfer failed with code {process.returncode}")

        except Exception as e:
            self.error_occurred.emit(str(e))

class FileListWorker(QThread):
    filesListed = pyqtSignal(list)
    errorOccurred = pyqtSignal(str)

    def __init__(self, directory, device=None, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.device = device

    def run(self):
        try:
            cmd = ["adb", "shell", "ls", "-p", self.directory]
            if self.device and self.device != "No Device":
                serial = self.device.split()[0]
                cmd = ["adb", "-s", serial, "shell", "ls", "-p", self.directory]
            
            result = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.PIPE)
            lines = result.splitlines()
            files = [line for line in lines if line.strip()]
            self.filesListed.emit(files)
        except subprocess.CalledProcessError as e:
            self.errorOccurred.emit(str(e))

class AdbCommandWorker(QThread):
    finished_with_output = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)

    def __init__(self, command, device=None, parent=None):
        super().__init__(parent)
        self.command = command
        self.device = device

    def run(self):
        try:
            cmd = self.command
            if self.device and self.device != "No Device":
                serial = self.device.split()[0]
                if cmd[0] == "adb":
                    cmd = ["adb", "-s", serial] + cmd[1:]
            
            output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.PIPE)
            self.finished_with_output.emit(output)
        except subprocess.CalledProcessError as e:
            self.errorOccurred.emit(str(e))

class ZipWorker(QThread):
    # Update signals to match expectation
    progress_update = pyqtSignal(str, int, str, str)
    finished = pyqtSignal()
    
    def __init__(self, items, current_directory, save_path, device=None, parent=None):
        super().__init__(parent)
        self.items = items 
        self.current_directory = current_directory
        self.save_path = save_path
        self.device = device
        self.is_running = True

    def run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            files_to_download = [f for f in self.items if not f.endswith("/")]
            total_files = len(files_to_download)
            if total_files == 0:
                self.progress_update.emit("Finished", 100, "", "")
                self.finished.emit()
                return

            completed_files = 0
            serial = self.device.split()[0] if (self.device and self.device != "No Device") else None

            for file_name in files_to_download:
                if not self.is_running: break
                
                cmd = ["adb", "pull", "-p", f"{self.current_directory}/{file_name}", temp_dir]
                if serial:
                    cmd = ["adb", "-s", serial, "pull", "-p", f"{self.current_directory}/{file_name}", temp_dir]
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                buffer = ""
                while True:
                    char = process.stdout.read(1)
                    if not char and process.poll() is not None:
                        break
                    
                    if char in ['\r', '\n']:
                        if buffer:
                            line = buffer.strip()
                            speed_match = re.search(r'(\d+\.?\d+\s*[KMG]?B/s)', line)
                            spd = speed_match.group(1) if speed_match else ""
                            
                            match = re.search(r'(\d+)%', line)
                            file_pct = int(match.group(1)) if match else 0
                            
                            overall_pct = int(((completed_files + (file_pct/100.0)) / total_files) * 100)
                            self.progress_update.emit(f"Downloading {file_name}", overall_pct, spd, "")
                            buffer = ""
                    else:
                        buffer += char

                process.wait()
                completed_files += 1
                
            # Zip creation
            self.progress_update.emit("Zipping files...", 99, "", "")
            with zipfile.ZipFile(self.save_path, 'w') as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, arcname=file)
            
            self.finished.emit()

class MultiDownloadWorker(QThread):
    progress_update = pyqtSignal(str, int, str, str) # title, pct, speed, eta
    finished = pyqtSignal()
    
    def __init__(self, items, current_directory, dest_folder, device=None, parent=None):
        super().__init__(parent)
        self.items = items
        self.current_directory = current_directory
        self.dest_folder = dest_folder
        self.device = device
        self.is_running = True

    def run(self):
        total_files = len(self.items)
        if total_files == 0:
            self.finished.emit()
            return

        serial = self.device.split()[0] if (self.device and self.device != "No Device") else None
        completed_files = 0
        
        for file_name in self.items:
            if not self.is_running: break
            
            target_path = os.path.join(self.dest_folder, file_name)
            cmd = ["adb", "pull", "-p", f"{self.current_directory}/{file_name}", target_path]
            if serial:
                cmd = ["adb", "-s", serial, "pull", "-p", f"{self.current_directory}/{file_name}", target_path]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            buffer = ""
            while True:
                char = process.stdout.read(1)
                if not char and process.poll() is not None:
                    break
                
                if char in ['\r', '\n']:
                    if buffer:
                        line = buffer.strip()
                        match_pct = re.search(r'(\d+)%', line)
                        file_pct = int(match_pct.group(1)) if match_pct else 0
                        
                        spd = ""
                        speed_match = re.search(r'(\d+\.?\d+\s*[KMG]?B/s)', line)
                        if speed_match: spd = speed_match.group(1)
                        
                        overall_pct = int(((completed_files + (file_pct/100.0)) / total_files) * 100)
                        self.progress_update.emit(f"Downloading {file_name}", overall_pct, spd, "")
                        buffer = ""
                else:
                    buffer += char
            
            process.wait()
            completed_files += 1
            
        self.finished.emit()
