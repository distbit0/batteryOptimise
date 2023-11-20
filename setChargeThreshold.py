import sys
import os


batterName = "BATT"
defaultThreshold = 60


def set_charge_threshold(threshold):
    command = f"sudo echo {threshold} > /sys/class/power_supply/{batterName}/charge_control_end_threshold"
    os.system('/bin/bash -c "' + command + '"')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "-h":
        set_charge_threshold(100)
    else:
        set_charge_threshold(defaultThreshold)


if __name__ == "__main__":
    # raise exception if not run as root
    if os.getuid() != 0:
        raise Exception("This script must be run as root")

    main()
