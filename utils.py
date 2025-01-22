import os
import pwd
import glob
import time
import json
import psutil
import logging
import subprocess
from datetime import datetime, timedelta
from os import path
from logging.handlers import TimedRotatingFileHandler

HISTORY_DURATION_MINUTES = 10


# File Operations
def read_file(path):
    matching_files = glob.glob(path)
    if not matching_files:
        raise FileNotFoundError(f"No files found matching the pattern: {path}")
    with open(matching_files[0], "r") as file:
        return file.read().strip()


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    return path.abspath(path.join(basepath, relPath))


# Command Execution
def execute_command(command, timeout=2):
    timeout = int(timeout)
    try:
        logging.info(f"Executing command: {command}")
        result = subprocess.run(
            ["bash", "-c", command],
            timeout=timeout,
            text=True,
            capture_output=True,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            logging.error(
                f"Command failed with status {result.returncode}: {result.stderr}"
            )
    except subprocess.TimeoutExpired as e:
        logging.warning(f"Command timed out after {timeout} seconds")
        output = e.stdout if e.stdout else ""
    except Exception as e:
        logging.error(f"Command execution error: {type(e).__name__}")
        output = ""
    return output if isinstance(output, str) else ""


# Battery Status Functions
class BatteryStatus:
    @staticmethod
    def get_charge():
        """Read current battery charge in microampere-hours"""
        try:
            return float(read_file("/sys/class/power_supply/BAT*/charge_now"))
        except:
            return float(read_file("/sys/class/power_supply/BAT*/energy_now"))

    @staticmethod
    def get_full_capacity():
        try:
            return float(read_file("/sys/class/power_supply/BAT*/charge_full"))
        except:
            return float(read_file("/sys/class/power_supply/BAT*/energy_full"))

    @staticmethod
    def get_end_threshold():
        try:
            return float(
                read_file("/sys/class/power_supply/BAT*/charge_control_end_threshold")
            )
        except:
            return 100.0

    @staticmethod
    def get_voltage():
        try:
            return float(read_file("/sys/class/power_supply/BAT*/voltage_now")) / 1e6
        except:
            return 0.0

    @staticmethod
    def get_ac_status():
        return read_file("/sys/class/power_supply/AC*/online")

    @staticmethod
    def get_percentage():
        return int(
            (BatteryStatus.get_charge() / BatteryStatus.get_full_capacity()) * 100
        )


# Charge History Management
class ChargeHistory:
    def __init__(self, history_file):
        self.history_file = history_file
        self.entries = self.load()
        # Check for direction change immediately upon loading
        self.check_direction_change()

    def load(self):
        entries = []
        if os.path.exists(self.history_file):
            cutoff_time = time.time() - (HISTORY_DURATION_MINUTES * 60)
            with open(self.history_file, "r") as f:
                for line in f:
                    try:
                        ts_str, ch_str = line.strip().split(",")
                        ts = float(ts_str)
                        if ts >= cutoff_time:
                            entries.append((ts, float(ch_str)))
                    except (ValueError, IndexError):
                        continue
        return entries

    def save(self):
        with open(self.history_file, "w") as f:
            for ts, ch in self.entries:
                f.write(f"{ts},{ch}\n")

    def check_direction_change(self):
        """Clear history if charging direction has changed"""
        if len(self.entries) < 2:
            return

        battery = BatteryStatus()
        ac_state = battery.get_ac_status()
        new_direction = 1 if ac_state == "1" else -1

        old_direction = self.get_charge_direction()
        if old_direction != 0 and old_direction != new_direction:
            logging.info("Charging direction changed, clearing history")
            self.entries.clear()

    def add_entry(self, charge):
        current_time = time.time()

        # Check direction change before adding new entry
        self.check_direction_change()

        self.entries.append((current_time, charge))
        self.entries = [
            (ts, ch)
            for ts, ch in self.entries
            if current_time - ts <= HISTORY_DURATION_MINUTES * 60
        ]

    def get_charge_direction(self):
        fullCharge = (
            BatteryStatus.get_end_threshold() * BatteryStatus.get_full_capacity() / 100
        )
        isFullyCharged = self.entries[-1][1] == fullCharge
        battery = BatteryStatus()
        ac_state = battery.get_ac_status()
        if len(self.entries) < 2:
            self.add_entry(BatteryStatus.get_charge())
            return (
                self.get_charge_direction()
            )  # recurse until it can return a valid value
        oldEntry = self.entries[-min(3, len(self.entries))]
        if self.entries[-1][1] > oldEntry[1]:
            return 1
        elif self.entries[-1][1] < oldEntry[1]:
            return -1
        elif self.entries[-1][1] == oldEntry[1]:
            if isFullyCharged and ac_state == "1":  # i.e. full charge hence on ac
                return 1
            return 0

    def calculate_power_metrics(self, voltage):
        if len(self.entries) < 2:
            return 0.0, 0.0

        # Calculate instantaneous power
        t1, c1 = self.entries[-min(4, len(self.entries))]
        t2, c2 = self.entries[-1]
        hours_diff = (t2 - t1) / 3600
        charge_diff = c2 - c1
        instant_power = voltage * (charge_diff / 1e6) / hours_diff

        # Calculate average power over entire history
        t_first, c_first = self.entries[0]
        total_hours = (t2 - t_first) / 3600
        total_charge_diff = c2 - c_first
        avg_power = voltage * (total_charge_diff / 1e6) / total_hours

        return instant_power, avg_power


# System User Functions
class SystemUser:
    @staticmethod
    def get_real_user():
        real_users = []
        for pw in pwd.getpwall():
            if (
                pw.pw_uid >= 1000
                and pw.pw_dir.startswith("/home/")
                and os.path.exists(pw.pw_dir)
            ):
                real_users.append((pw.pw_name, pw.pw_dir))

        if len(real_users) == 1:
            return real_users[0]
        elif len(real_users) > 1:
            return SystemUser._find_most_recent_user(real_users)
        return None, None

    @staticmethod
    def _find_most_recent_user(users):
        latest_user = None
        latest_time = 0
        for username, homedir in users:
            for check_file in [".profile", ".bashrc", ".bash_history"]:
                file_path = os.path.join(homedir, check_file)
                try:
                    if os.path.exists(file_path):
                        mtime = os.path.getmtime(file_path)
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_user = (username, homedir)
                except (OSError, PermissionError):
                    continue
        return latest_user if latest_user else (None, None)


# Logging Configuration
def configure_logging(log_name):
    log_dir = getAbsPath("logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, f"{log_name}.log"),
        when="midnight",
        interval=1,
        backupCount=1,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# State Management
class StateManager:
    def __init__(self, state_file):
        self.state_file = state_file

    def read_state(self):
        if not os.path.exists(self.state_file):
            default_state = {"last_execution_mode": "onAC", "last_execution_time": None}
            self.write_state(default_state)
            return default_state
        with open(self.state_file, "r") as f:
            return json.load(f)

    def write_state(self, state):
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)
