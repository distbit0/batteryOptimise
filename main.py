import argparse
import os
from os import path


# Parsing command-line arguments
parser = argparse.ArgumentParser(description="Optimise battery")
parser.add_argument(
    "--username", default=None, help="Specify username to construct home directory path"
)


commands = [
    [
        "Change laptop mode to improve disk idleness",
        "echo 5 > /proc/sys/vm/laptop_mode",
    ],
    [
        "Disable Non-Maskable Interrupt watchdog",
        "echo 0 > /proc/sys/kernel/nmi_watchdog",
    ],
    [
        "Set power-saving mode for Intel HD audio",
        "echo 1 > /sys/module/snd_hda_intel/parameters/power_save",
    ],
    [
        "Control power-saving for Intel HD audio controller",
        "echo Y > /sys/module/snd_hda_intel/parameters/power_save_controller",
    ],
    [
        "(Commented) Set multicore power saving",
        "#echo 1 > /sys/devices/system/cpu/sched_mc_power_savings",
    ],
    [
        "(Commented) Set CPU frequency scaling to ondemand",
        "#echo ondemand | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
    ],
    [
        "Set CPU frequency scaling to powersave",
        "echo powersave | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor",
    ],
    ["Set dirty writeback time", "echo 1500 > /proc/sys/vm/dirty_writeback_centisecs"],
    [
        "(Commented) Set PCIe power management policy to powersupersave",
        "#echo powersupersave > /sys/module/pcie_aspm/parameters/policy",
    ],
    [
        "Set PCIe power management policy to powersave",
        "echo powersave > /sys/module/pcie_aspm/parameters/policy",
    ],
    [
        "(Commented) Set USB autosuspend",
        "#for i in /sys/bus/usb/devices/*/power/autosuspend; do echo 1 > $i; done",
    ],
    [
        "(Commented) Set PCI device power level",
        "#for i in /sys/bus/pci/devices/*/power_level ; do echo 5 > $i ; done 2>/dev/null",
    ],
    [
        "Adjust power states on Ryzen CPUs",
        "/home/pimania/apps/RyzenAdj/build/ryzenadj -a 15000 -b 30000 -c 20000 --power-saving",
    ],
    [
        "Set GPU power state to battery",
        "echo battery > /sys/class/drm/card0/device/power_dpm_state",
    ],
    [
        "Force GPU specific performance level",
        "echo manual > /sys/class/drm/card0/device/power_dpm_force_performance_level",
    ],
    [
        "Set GPU power profile mode",
        "echo 2 > /sys/class/drm/card0/device/pp_power_profile_mode",
    ],
    ["Disable CPU boosting", "echo 0 > /sys/devices/system/cpu/cpufreq/boost"],
    ["Powertop autotune", "powertop --auto-tune"],
    ["Start auto cpufreq", "auto-cpufreq --install"],
    ["Install TLP config file", "cp $$$/tlp.conf /etc"],
    ["Enable TLP service", "systemctl enable --now tlp.service"],
    ["Enable thermald service", "systemctl enable --now thermald.service"],
]


def addAMDPstateToGrubConfig():
    # check if if it is configured
    if "amd_pstate" in open("/etc/default/grub").read():
        print("AMD P-State already configured")
        return
    else:
        reconstructedConfig = []
        for line in open("/etc/default/grub").read().split("\n"):
            if "GRUB_CMDLINE_LINUX_DEFAULT" in line:
                value = line.split("=")[1][1:-1]
                newValue = (
                    value
                    + " amd_pstate=passive initcall_blacklist=acpi_cpufreq_init amd_pstate.shared_mem=1"
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

    if args.username:
        home_directory = f"/home/{args.username}"
    else:
        home_directory = os.path.expanduser("~")

    executeCommands(home_directory)
    addAMDPstateToGrubConfig()
