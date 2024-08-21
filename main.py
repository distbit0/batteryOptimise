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
        print("Executing command:", command)
        output = (
            subprocess.check_output(command, shell=True, timeout=timeout)
            .decode()
            .strip()
        )
    except Exception as e:
        if not sys.exc_info()[0] == subprocess.TimeoutExpired:
            print("Command execution error:", sys.exc_info()[0], command)
            # traceback.print_exc()
        output = e.output.decode().strip() if e.output else ""
    return output


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
    return_code = os.system("auto-cpufreq --version")
    if return_code == 0:
        print("auto-cpufreq is already installed")
    else:
        print("Installing auto-cpufreq")
        execute_command(
            "git clone https://github.com/AdnanHodzic/auto-cpufreq.git; cd auto-cpufreq; ./auto-cpufreq-installer; cd .. && rm -rf auto-cpufreq"
        )


def add_amd_pstate_to_grub_config():
    grub_file = "/etc/default/grub"
    if (
        "amd_pstate" in open(grub_file).read()
        or "pstate"
        in open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver").read()
    ):
        print("AMD P-State already configured")
        return

    reconstructed_config = []
    for line in open(grub_file).read().split("\n"):
        if "GRUB_CMDLINE_LINUX_DEFAULT" in line:
            value = line.split("=")[1][1:-1]
            new_value = (
                value + " amd_pstate=guided initcall_blacklist=acpi_cpufreq_init"
            )
            reconstructed_config.append(f'GRUB_CMDLINE_LINUX_DEFAULT="{new_value}"')
        else:
            reconstructed_config.append(line)

    with open(grub_file, "w") as file:
        file.write("\n".join(reconstructed_config))
    execute_command("update-grub")


def replace_placeholders(command, config):
    return command.replace("$$$", getAbsPath("")).replace("~", config["home_directory"])


def main():
    config = read_config("config.json")
    current_battery_mode = is_on_battery() or config["alwaysUseBatteryMode"]
    mode_config = config["battery_mode"] if current_battery_mode else config["ac_mode"]

    # last_execution_time = mode_config["last_execution_time"]
    # execution_interval = mode_config["execution_interval"]
    last_battery_mode = config["last_execution_mode"]

    if last_battery_mode == current_battery_mode:
        print(
            f"This command was last executed in {'battery' if current_battery_mode else 'AC'} mode. Which is the same as the current mode. Exiting."
        )
        exit(0)

    if current_battery_mode:
        install_auto_cpufreq()
        if config["setAMDPstate"]:
            add_amd_pstate_to_grub_config()

    commands = [
        [replace_placeholders(cmd[0], config), cmd[1]]
        for cmd in mode_config["commands"]
    ]
    execute_commands(commands)

    # mode_config["last_execution_time"] = time.time()
    config["last_execution_mode"] = current_battery_mode
    write_config("config.json", config)


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    main()
