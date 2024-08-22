import sys
import json
from datetime import datetime, timedelta
from os import path


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def update_config(mode):
    """
    Update the config.json file based on the power mode.
    """
    config_file = getAbsPath("config.json")
    with open(config_file, "r") as file:
        config = json.load(file)

    if mode == "bat":
        config["alwaysCpuBatteryMode"] = True
        config["alwaysBrightnessBatteryMode"] = True
        config["last_auto_state"] = {
            "alwaysCpuBatteryMode": config.get("alwaysCpuBatteryMode", False),
            "alwaysBrightnessBatteryMode": config.get(
                "alwaysBrightnessBatteryMode", False
            ),
        }
    elif mode == "auto":
        if "last_auto_state" in config:
            config["alwaysCpuBatteryMode"] = config["last_auto_state"][
                "alwaysCpuBatteryMode"
            ]
            config["alwaysBrightnessBatteryMode"] = config["last_auto_state"][
                "alwaysBrightnessBatteryMode"
            ]
            del config["last_auto_state"]

    with open(config_file, "w") as file:
        json.dump(config, file, indent=2)


def save_relative_timestamp(hours):
    """
    Save a timestamp 'hours' in the future to a file.
    """
    future_time = datetime.now() + timedelta(hours=hours)
    with open(timestamp_file, "w") as file:
        file.write(future_time.strftime("%Y-%m-%d %H:%M:%S"))


def is_past_timestamp():
    """
    Check if the current time is past the saved timestamp.
    Returns True only once, then updates the file to prevent future True returns.
    """
    try:
        with open(timestamp_file, "r") as file:
            saved_time = file.read().strip()
            if saved_time == "":
                return False
            saved_time = datetime.strptime(saved_time, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > saved_time:
                with open(timestamp_file, "w") as write_file:
                    write_file.write("")
                return True
            return False
    except FileNotFoundError:
        return False  # No timestamp file found, default to False


def main():
    if len(sys.argv) != 2:
        print("Usage: script.py [keyboard|cron]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "keyboard":
        if not is_past_timestamp():
            print("Setting to AUTO mode.")
            update_config("auto")
            save_relative_timestamp(-3)
        else:
            print("Setting to BATTERY mode.")
            update_config("bat")
            save_relative_timestamp(3)
    elif mode == "cron":
        if is_past_timestamp():
            update_config("auto")
    else:
        print("Invalid mode. Use 'keyboard' or 'cron'.")


if __name__ == "__main__":
    timestamp_file = getAbsPath("timestamp.txt")
    main()
