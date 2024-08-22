import os
import json
import time
import subprocess
from os import path
import sys
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

    last_execution_mode = config["last_execution_mode"]
    currentExecutionMode = (
        str(isOnBattery) + str(alwaysCpuBatteryMode) + str(alwaysBrightnessBatteryMode)
    )
    if last_execution_mode == currentExecutionMode:
        print(
            f"This command was last executed in {'battery' if isOnBattery else 'AC'} mode. Which is the same as the current mode. Exiting."
        )
        exit(0)

    if isOnBattery:
        install_auto_cpufreq()

    execute_commands(
        [
            [replace_placeholders(cmd[0], config), cmd[1]]
            for cmd in cpuCommands + brightnessCommands
        ]
    )

    config["last_execution_mode"] = currentExecutionMode
    write_config("config.json", config)


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    main()
