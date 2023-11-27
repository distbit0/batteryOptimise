import sys
import os
import subprocess

batteryName = "BATT"
defaultThreshold = 80
fullThreshold = 100


def set_charge_threshold(threshold):
    command = f"sudo echo {threshold} > /sys/class/power_supply/{batteryName}/charge_control_end_threshold"
    os.system('/bin/bash -c "' + command + '"')


def get_charge_threshold():
    command = f"/bin/bash -c 'cat /sys/class/power_supply/{batteryName}/charge_control_end_threshold'"
    output = subprocess.check_output(command, shell=True).decode().strip()
    return int(output)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        currentThreshold = get_charge_threshold()
        if currentThreshold == fullThreshold:
            print(f"Setting threshold to {defaultThreshold}%.")
            set_charge_threshold(defaultThreshold)
        else:
            print(f"Setting threshold to {fullThreshold}%.")
            set_charge_threshold(fullThreshold)
    else:
        set_charge_threshold(defaultThreshold)


if __name__ == "__main__":
    # raise exception if not run as root
    if os.getuid() != 0:
        raise Exception("This script must be run as root")

    main()
