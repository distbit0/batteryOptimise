import argparse
import os
from os import path


# Parsing command-line arguments
parser = argparse.ArgumentParser(description="Optimise battery")
parser.add_argument(
    "--username", default=None, help="Specify username to construct home directory path"
)

commands = [
    # [
    #     "Install laptop mode config files",
    #     "cp $$$/laptop-mode.conf /etc/laptop-mode/; cp $$$/laptop-mode-cpufreq.conf /etc/laptop-mode/conf.d/cpufreq.conf",
    # ],
    ["Powertop autotune", "powertop --auto-tune"],
    ["Start auto cpufreq", "auto-cpufreq --install"],
    ["Install TLP config file", "cp $$$/tlp.conf /etc"],
    ["Enable TLP service", "systemctl enable --now tlp.service"],
    # ["Enable thermald service", "systemctl enable --now thermald.service"], does not work on amd
    # ["Enable laptop mode service", "systemctl enable --now laptop-mode.service"],
]


def installAutocpufreq():
    # check if it is installed
    return_code = os.system("auto-cpufreq --version")
    if return_code == 0:
        print("autocpufreq is already installed")
    else:
        print("Installing autocpufreq")
        os.system(
            "git clone https://github.com/AdnanHodzic/auto-cpufreq.git; cd auto-cpufreq; ./auto-cpufreq-installer; cd .. && rm -rf auto-cpufreq"
        )


def addAMDPstateToGrubConfig():
    if (
        "amd_pstate" in open("/etc/default/grub").read()
        or "pstate"
        in open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_driver").read()
    ):
        print("AMD P-State already configured")
        return
    else:
        reconstructedConfig = []
        for line in open("/etc/default/grub").read().split("\n"):
            if "GRUB_CMDLINE_LINUX_DEFAULT" in line:
                value = line.split("=")[1][1:-1]
                newValue = (
                    value + " amd_pstate=guided initcall_blacklist=acpi_cpufreq_init"
                )
                reconstructedConfig.append(f'GRUB_CMDLINE_LINUX_DEFAULT="{newValue}"')
            else:
                reconstructedConfig.append(line)

        with open("/etc/default/grub", "w") as file:
            file.write("\n".join(reconstructedConfig))

        os.system("update-grub")


def replace_tilde_with_home_directory(command, home_directory):
    return command.replace("~", home_directory)


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def replace_dollars_with_current_directory(command):
    currentDirectory = getAbsPath(".")
    return command.replace("$$$", currentDirectory)


def print_and_execute_command(description, command, home_directory):
    command = replace_tilde_with_home_directory(command, home_directory)
    command = replace_dollars_with_current_directory(command)
    print("\n" + description, ":", command + "\n")
    return_code = os.system(command)
    if return_code != 0:
        print(f"Error: Command returned with code {return_code}")


def executeCommands(home_directory):
    for command in commands:
        print_and_execute_command(command[0], command[1], home_directory)


if __name__ == "__main__":
    args = parser.parse_args()

    # abort if not run with sudo
    if not os.geteuid() == 0:
        print("This script must be run as root")
        exit(1)

    if args.username:
        home_directory = f"/home/{args.username}"
    else:
        home_directory = os.path.expanduser("~")

    installAutocpufreq()
    executeCommands(home_directory)
    # addAMDPstateToGrubConfig()
