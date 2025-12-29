import subprocess
import logging

class AdbManager:
    @staticmethod
    def get_devices():
        try:
            output = subprocess.check_output(["adb", "devices"], universal_newlines=True, stderr=subprocess.PIPE)
            lines = output.strip().splitlines()[1:]
            devices = []
            for line in lines:
                if line.strip() and ("device" in line or "unauthorized" in line):
                    parts = line.split()
                    device_id = parts[0]
                    # WiFi check logic can be added here if needed, but keeping it simple for now
                    if ":" in device_id:
                        device_id += " (WiFi)"
                    devices.append(device_id)
            return devices
        except subprocess.CalledProcessError:
            return []

    @staticmethod
    def build_command(base_command, device_id=None):
        """
        Injects the -s <device_id> into the command if a device is specified.
        Assumes base_command is a list, e.g. ["adb", "shell", "ls"]
        """
        if device_id and device_id != "No Device":
            # Remove (WiFi) suffix if processing it for command
            real_id = device_id.split()[0]
            # Insert -s <device> after "adb"
            if base_command[0] == "adb":
                return ["adb", "-s", real_id] + base_command[1:]
        return base_command
