import os
import pwd
import glob
import time
from datetime import datetime, timedelta
import json
import time
import subprocess
from os import path
import psutil
import logging
from logging.handlers import TimedRotatingFileHandler


def read_file(path):
    matching_files = glob.glob(path)
    if not matching_files:
        raise FileNotFoundError(f"No files found matching the pattern: {path}")

    # Use the first matching file
    file_path = matching_files[0]
    with open(file_path, "r") as file:
        return file.read().strip()


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def execute_command(command, timeout=2):
    timeout = int(timeout)
    try:
        print("\nExecuting command:", command)
        result = subprocess.run(
            ['bash', '-c', command],  # Use bash explicitly
            timeout=timeout,
            text=True,
            capture_output=True
        )
        print("output:", result.stdout, result.stderr)
        output = result.stdout.strip()
        if result.returncode != 0:
            logging.error(f"Command exited with non-zero status: {result.returncode}")
            logging.error(f"Error output: {result.stderr.strip()}")
    except subprocess.TimeoutExpired as e:
        logging.warning(f"Command timed out after {timeout} seconds")
        output = e.stdout if e.stdout else ""
    except Exception as e:
        logging.error(f"Command execution error: {type(e).__name__}")
        output = ""
    return output if type(output) == str else ""

def is_on_battery():
    commands = read_config("config.json")["batteryCheckCommands"]
    for command in commands:
        if commands[command].lower() in execute_command(command).lower():
            try:
                current_now = float(read_file("/sys/class/power_supply/BAT*/current_now"))
                voltage_now = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))
                power_consumption = current_now * voltage_now / 10**12
            except:
                power_consumption = float(read_file("/sys/class/power_supply/BAT*/power_now")) / 10**6
            # to avoid false positives where battery is neither charging nor discharging
            if power_consumption > 2:
                return True
    return False


def is_executed_recently(last_execution_time, execution_interval):
    current_time = time.time()
    return current_time - last_execution_time < execution_interval


def read_config(config_file):
    with open(getAbsPath(config_file), "r") as file:
        return json.load(file)

def read_execution_state():
    state_file = getAbsPath("execution_state.json")
    if not os.path.exists(state_file):
        # Initialize with default values
        default_state = {
            "last_execution_mode": "onAC",
            "last_execution_time": None
        }
        with open(state_file, "w") as f:
            json.dump(default_state, f, indent=2)
        return default_state
    
    with open(state_file, "r") as f:
        return json.load(f)

def write_execution_state(state):
    state_file = getAbsPath("execution_state.json")
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def execute_commands(commands):
    for command in commands:
        command, timeout = command
        execute_command(command, timeout)

def replace_placeholders(command, config):
    home_directory = get_real_user()[1]
    return command.replace("$$$", getAbsPath("")).replace("~", home_directory)


def should_execute(execution_state, current_execution_mode):
    last_execution_mode = execution_state["last_execution_mode"]
    last_execution_time = execution_state.get("last_execution_time")

    # Define the minimum time interval between executions (e.g., 1 hour)
    min_interval = timedelta(hours=config["min_execution_interval"])

    # Get current time and system boot time
    current_time = datetime.now()
    boot_time = datetime.fromtimestamp(psutil.boot_time())

    # Check if sufficient time has elapsed or if the execution mode has changed
    time_elapsed = (
        current_time - datetime.fromisoformat(last_execution_time)
        if last_execution_time
        else min_interval  # Ensure it runs on first execution
    )

    mode_changed = last_execution_mode != current_execution_mode
    time_elapsed_sufficient = time_elapsed >= min_interval

    # Check if the system has rebooted since last execution
    system_rebooted = last_execution_time is None or boot_time > datetime.fromisoformat(
        last_execution_time
    )

    should_run = mode_changed or time_elapsed_sufficient or system_rebooted

    if not should_run:
        logging.info(
            f"Last executed {time_elapsed.total_seconds() / 3600:.2f} hours ago. "
            f"Current mode is the same, not enough time has elapsed, "
            f"and no system reboot detected."
        )
        return False, current_time, time_elapsed

    # If we're running due to a reboot, update the message
    if system_rebooted:
        logging.info("System reboot detected. Executing...")
    elif mode_changed:
        logging.info("Execution mode has changed. Executing...")
    else:
        logging.info(
            f"Sufficient time ({time_elapsed.total_seconds() / 3600:.2f} hours) has elapsed. Executing..."
        )

    return True, current_time, time_elapsed

def get_real_user():
    """
    Attempts to find the real user even when running as root from crontab.
    Returns tuple of (username, home_directory).
    """
    # First try getting all non-system users
    real_users = []
    
    for pw in pwd.getpwall():
        # Filter for real users (typically UID >= 1000 on modern Linux)
        # and having a home directory in /home/
        if (pw.pw_uid >= 1000 and 
            pw.pw_dir.startswith('/home/') and 
            os.path.exists(pw.pw_dir)):
            real_users.append((pw.pw_name, pw.pw_dir))
    
    # If we find exactly one real user, return their info
    if len(real_users) == 1:
        return real_users[0]
    
    # If we found multiple users, try to find the most recently modified home directory
    elif len(real_users) > 1:
        latest_user = None
        latest_time = 0
        
        for username, homedir in real_users:
            try:
                # Check the modification time of the user's .profile or similar
                for check_file in ['.profile', '.bashrc', '.bash_history']:
                    file_path = os.path.join(homedir, check_file)
                    if os.path.exists(file_path):
                        mtime = os.path.getmtime(file_path)
                        if mtime > latest_time:
                            latest_time = mtime
                            latest_user = (username, homedir)
            except (OSError, PermissionError):
                continue
                
        if latest_user:
            return latest_user
    
    return None, None

def check_screen_lock_status(regular_user, dbus_address):
    # First try GNOME screensaver
    gdbus_command = (
        f"DBUS_SESSION_BUS_ADDRESS={dbus_address} "
        f"gdbus call --session --dest org.gnome.ScreenSaver "
        f"--object-path /org/gnome/ScreenSaver "
        f"--method org.gnome.ScreenSaver.GetActive"
    )
    
    lock_status = execute_command(
        f"su -m {regular_user} -c '{gdbus_command}'"
    )
    
    if lock_status and "true" in lock_status.lower():
        logging.info(f"Screen is locked (GNOME). Lock status output: {lock_status}")
        return False

    # Try XScreenSaver
    xscreensaver_command = f"su -m {regular_user} -c 'xscreensaver-command -time 2>/dev/null'"
    xss_status = execute_command(xscreensaver_command)
    
    if xss_status and "screen locked" in xss_status.lower():
        logging.info(f"Screen is locked (XScreenSaver). Lock status output: {xss_status}")
        return False

    # Try X11 screensaver
    x11_command = f"su -m {regular_user} -c 'xset q 2>/dev/null | grep \"DPMS is Enabled\"'"
    x11_status = execute_command(x11_command, )
    
    if x11_status:
        # Check if screen is in power saving mode
        dpms_command = f"su -m {regular_user} -c 'xset q 2>/dev/null | grep \"Monitor is\"'"
        dpms_status = execute_command(dpms_command, )
        
        if dpms_status and any(state in dpms_status.lower() for state in ["standby", "suspended", "off"]):
            logging.info(f"Screen is in power saving mode (X11). Status: {dpms_status}")
            return False

    # If we get here, assume screen is not locked
    return True



def is_screen_on_and_unlocked():
    """
    Checks if the screen is on and unlocked for the regular user.
    Returns True if the screen is on and unlocked, False otherwise.
    """
    # Determine the regular user by looking at name of their folder in home directory
    regular_user = get_real_user()[0]
    if not regular_user:
        logging.error("Unable to determine the regular user.")
        return False

    try:
        # Get the UID of the regular user using the pwd module
        uid = pwd.getpwnam(regular_user).pw_uid
    except KeyError:
        logging.error(f"User '{regular_user}' not found.")
        return False

    # Construct the DBus session address
    dbus_address = f'unix:path=/run/user/{uid}/bus'

    # Command to check if the user's session is active
    logging.debug(f"Regular user: {regular_user}")
    session_status = execute_command(
        f"su -m {regular_user} -c 'loginctl show-session $(loginctl show-user {regular_user} -p Display --value) -p State --value'"
    )
    if "active" not in session_status.lower():
        logging.info(f"Session is not active. Status: {session_status}")
        return False

    unlocked = check_screen_lock_status(regular_user, dbus_address)
    if not unlocked:
        logging.info("Screen is locked. Not executing command.")
        return False

    logging.info("Screen is on and unlocked.")
    return True

def configure_logging():
    # Create logs directory if it doesn't exist
    log_dir = getAbsPath("logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Set up logging configuration
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add timed rotating file handler (rotates daily, keeps 1 day)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, 'power_mode.log'),
        when='midnight',
        interval=1,
        backupCount=1
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def main():
    configure_logging()
    logging.info("Starting power mode script")
    config = read_config("config.json")
    execution_state = read_execution_state()
    isOnBattery = is_on_battery()

    recurringCommands = (
        config["battery_mode"]["commands"]["recurring"]
        if isOnBattery
        else config["ac_mode"]["commands"]["recurring"]
    )
    oneTimeCommands = (
        config["battery_mode"]["commands"]["oneTime"]
        if isOnBattery
        else config["ac_mode"]["commands"]["oneTime"]
    )

    currentExecutionMode = "onBattery" if isOnBattery else "onAC"

    executeOneTimeCommands, current_time, time_elapsed = should_execute(
        execution_state, currentExecutionMode
    )

    if executeOneTimeCommands:
        execute_commands(
            [[replace_placeholders(cmd[0], config), cmd[1]] for cmd in oneTimeCommands]
        )
        
        # Update the execution state
        execution_state["last_execution_mode"] = currentExecutionMode
        execution_state["last_execution_time"] = current_time.isoformat()
        write_execution_state(execution_state)
        logging.info(
            f"Executed ALL commands in {'battery' if isOnBattery else 'AC'} mode after {time_elapsed.total_seconds() / 3600:.2f} hours."
        )
    else:
        logging.info(
            f"Executed recurring commands in {'battery' if isOnBattery else 'AC'} mode after {time_elapsed.total_seconds() / 3600:.2f} hours."
        )
    # execute recurring commands anyway, because executing them is very non-compute-intensive, unlike oneTime commands
    if is_screen_on_and_unlocked(): 
        execute_commands(
            [[replace_placeholders(cmd[0], config), cmd[1]] for cmd in recurringCommands]
        )


if __name__ == "__main__":
    if not os.geteuid() == 0:
        logging.error("This script must be run as root")
        exit(1)

    main()
    # print(is_screen_on_and_unlocked())
