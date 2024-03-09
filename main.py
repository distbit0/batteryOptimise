import os
import json
import time
import subprocess
from os import path


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def is_on_battery():
    battery_info = subprocess.check_output(["acpi", "-b"]).decode("utf-8")
    return "Discharging" in battery_info


def is_executed_recently(last_execution_time, execution_interval):
    current_time = time.time()
    return current_time - last_execution_time < execution_interval


def execute_command(command):
    print(f"Executing: {command}")
    return_code = os.system(command)
    if return_code != 0:
        print(f"Error: Command returned with code {return_code}")


def read_config(config_file):
    with open(getAbsPath(config_file), "r") as file:
        return json.load(file)


def write_config(config_file, config):
    with open(getAbsPath(config_file), "w") as file:
        json.dump(config, file, indent=2)


def execute_commands(commands):
    for command in commands:
        execute_command(command)


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
    config_file = "config.json"
    config = read_config(config_file)

    battery_mode = is_on_battery()
    mode_config = config["battery_mode"] if battery_mode else config["ac_mode"]

    last_execution_time = mode_config["last_execution_time"]
    execution_interval = mode_config["execution_interval"]

    if is_executed_recently(last_execution_time, execution_interval):
        print(
            f"Commands have been executed recently in {'battery' if battery_mode else 'AC'} mode. Exiting."
        )
        exit(0)

    if battery_mode:
        install_auto_cpufreq()
        if config["setAMDPstate"]:
            add_amd_pstate_to_grub_config()

    commands = [replace_placeholders(cmd, config) for cmd in mode_config["commands"]]
    execute_commands(commands)

    mode_config["last_execution_time"] = time.time()
    write_config(config_file, config)


if __name__ == "__main__":
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    main()
