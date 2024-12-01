import os
import pwd
import glob
import time
from datetime import datetime, timedelta

import json
import time
import subprocess
from os import path
import sys
import psutil
import traceback
import pysnooper


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
            command, shell=True, timeout=timeout, text=True, capture_output=True
        )
        print("output:", result.stdout, result.stderr)
        output = result.stdout.strip()
        if result.returncode != 0:
            print(f"Command exited with non-zero status: {result.returncode}")
            print(f"Error output: {result.stderr.strip()}")
    except subprocess.TimeoutExpired as e:
        print(f"Command timed out after {timeout} seconds")
        output = e.stdout if e.stdout else ""
    except Exception as e:
        print(f"Command execution error: {type(e).__name__}", file=sys.stderr)
        output = ""
    return output if type(output) == str else ""


def is_on_battery():
    commands = read_config("config.json")["batteryCheckCommands"]
    for command in commands:
        if commands[command].lower() in execute_command(command).lower():
            current_now = float(read_file("/sys/class/power_supply/BAT*/current_now"))
            voltage_now = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))
            power_consumption = current_now * voltage_now / 10**12
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


def write_config(config_file, config):
    with open(getAbsPath(config_file), "w") as file:
        json.dump(config, file, indent=2)


def execute_commands(commands):
    for command in commands:
        command, timeout = command
        execute_command(command, timeout)


def install_auto_cpufreq():
    output = execute_command("auto-cpufreq --version")
    return_code = 1 if output == "" else 0
    if return_code == 0:
        print("auto-cpufreq is already installed")
    else:
        print("Installing auto-cpufreq")
        print(
            "INSTALL AUTOCPUFREQ WITH FOLLOWING COMMAND: sudo su; git clone https://github.com/AdnanHodzic/auto-cpufreq.git; cd auto-cpufreq; ./auto-cpufreq-installer && cd .. && rm -rf auto-cpufreq"
        )
        exit(1)
    output = execute_command("auto-cpufreq --stats")
    return_code = 1 if "auto-cpufreq not running" in output else 0
    if return_code == 0:
        print("auto-cpufreq is already installed")
    else:
        print("Installing auto-cpufreq")
        execute_command("sudo auto-cpufreq --install")


def replace_placeholders(command, config):
    return command.replace("$$$", getAbsPath("")).replace("~", config["home_directory"])


def should_execute(config, current_execution_mode):
    last_execution_mode = config["last_execution_mode"]
    last_execution_time = config.get("last_execution_time")

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
        print(
            f"Last executed {time_elapsed.total_seconds() / 3600:.2f} hours ago. "
            f"Current mode is the same, not enough time has elapsed, "
            f"and no system reboot detected. Exiting."
        )
        return False, current_time, time_elapsed

    # If we're running due to a reboot, update the message
    if system_rebooted:
        print("System reboot detected. Executing...")
    elif mode_changed:
        print("Execution mode has changed. Executing...")
    else:
        print(
            f"Sufficient time ({time_elapsed.total_seconds() / 3600:.2f} hours) has elapsed. Executing..."
        )

    return True, current_time, time_elapsed


def is_screen_on_and_unlocked():
    """
    Checks if the screen is on and unlocked for the regular user.
    Returns True if the screen is on and unlocked, False otherwise.
    """
    # Determine the regular user (the user who invoked sudo or the current user)
    regular_user = os.environ.get('SUDO_USER') or os.environ.get('USER')
    if not regular_user:
        print("Unable to determine the regular user.")
        return False

    try:
        # Get the UID of the regular user using the pwd module
        uid = pwd.getpwnam(regular_user).pw_uid
    except KeyError:
        print(f"User '{regular_user}' not found.")
        return False

    # Construct the DBus session address
    dbus_address = f'unix:path=/run/user/{uid}/bus'

    # Command to check if the user's session is active
    session_command = (
        f"loginctl show-session $(loginctl show-user {regular_user} -p Display --value) -p State --value"
    )
    session_status = execute_command(
        f"su -m {regular_user} -c '{session_command}'"
    )
    if "active" not in session_status.lower():
        print(f"Session is not active. Status: {session_status}")
        return False

    # Command to check if the screen is locked using GNOME's D-Bus interface
    gdbus_command = (
        f"DBUS_SESSION_BUS_ADDRESS={dbus_address} "
        f"gdbus call --session --dest org.gnome.ScreenSaver "
        f"--object-path /org/gnome/ScreenSaver "
        f"--method org.gnome.ScreenSaver.GetActive"
    )
    lock_status = execute_command(
        f"su -m {regular_user} -c '{gdbus_command}'"
    )

    # The output will be "(false,)" if the screen is unlocked, and "(true,)" if it's locked
    if "true" in lock_status.lower():
        print(f"Screen is locked. Lock status output: {lock_status}")
        return False

    print("Screen is on and unlocked.")
    return True

def main():
    config = read_config("config.json")
    isOnBattery = is_on_battery()
    alwaysCpuBatteryMode = config["alwaysCpuBatteryMode"]
    alwaysBrightnessBatteryMode = config["alwaysBrightnessBatteryMode"]

    brightnessCommands = (
        config["battery_mode"]["commands"]["brightness"]
        if alwaysBrightnessBatteryMode or isOnBattery
        else config["ac_mode"]["commands"]["brightness"]
    )
    cpuCommands = (
        config["battery_mode"]["commands"]["cpu"]
        if alwaysCpuBatteryMode or isOnBattery
        else config["ac_mode"]["commands"]["cpu"]
    )

    currentExecutionMode = (
        str(isOnBattery) + str(alwaysCpuBatteryMode) + str(alwaysBrightnessBatteryMode)
    )

    executeCPUCommands, current_time, time_elapsed = should_execute(
        config, currentExecutionMode
    )

    if executeCPUCommands:
        execute_commands(
            [[replace_placeholders(cmd[0], config), cmd[1]] for cmd in cpuCommands]
        )
        if isOnBattery or alwaysCpuBatteryMode:
            install_auto_cpufreq()
        # Update the last execution mode and time in the config
        config["last_execution_mode"] = currentExecutionMode
        config["last_execution_time"] = current_time.isoformat()
        write_config("config.json", config)
        print(
            f"Executed ALL commands in {'battery' if isOnBattery else 'AC'} mode after {time_elapsed.total_seconds() / 3600:.2f} hours."
        )
    else:
        print(
            f"Executed BRIGHTNESS commands in {'battery' if isOnBattery else 'AC'} mode after {time_elapsed.total_seconds() / 3600:.2f} hours."
        )
    # execute brightness commands anyway, because executing them is very non-compute-intensive, unlike cpu commands
    if is_screen_on_and_unlocked(): 
        execute_commands(
            [[replace_placeholders(cmd[0], config), cmd[1]] for cmd in brightnessCommands]
        )


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    main()
    # print(is_screen_on_and_unlocked())
