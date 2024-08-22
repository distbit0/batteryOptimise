import os
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
        execute_command(
            "git clone https://github.com/AdnanHodzic/auto-cpufreq.git; cd auto-cpufreq; ./auto-cpufreq-installer && cd .. && rm -rf auto-cpufreq"
        )
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

    execute, current_time, time_elapsed = should_execute(config, currentExecutionMode)

    if not execute:
        exit(0)

    if isOnBattery:
        install_auto_cpufreq()

    execute_commands(
        [
            [replace_placeholders(cmd[0], config), cmd[1]]
            for cmd in cpuCommands + brightnessCommands
        ]
    )

    # Update the last execution mode and time in the config
    config["last_execution_mode"] = currentExecutionMode
    config["last_execution_time"] = current_time.isoformat()
    write_config("config.json", config)

    print(
        f"Executed in {'battery' if isOnBattery else 'AC'} mode after {time_elapsed.total_seconds() / 3600:.2f} hours."
    )


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    main()
