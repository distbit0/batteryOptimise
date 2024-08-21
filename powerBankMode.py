import sys
import subprocess
from datetime import datetime, timedelta
from os import path


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def set_power_mode(mode):
    """
    Set the power mode for both tlp and auto-cpufreq.
    """
    if mode == "bat":
        subprocess.run(["sudo", "tlp", "bat"])
        subprocess.run(["sudo", "auto-cpufreq", "--force=powersave"])
    elif mode == "auto":
        subprocess.run(["sudo", "tlp", "start"])
        subprocess.run(["sudo", "auto-cpufreq", "--force=reset"])
    else:
        print(f"Unknown mode: {mode}")


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
            set_power_mode("auto")
            save_relative_timestamp(-3)
        else:
            print("Setting to BATTERY mode.")
            set_power_mode("bat")
            save_relative_timestamp(3)
    elif mode == "cron":
        if is_past_timestamp():
            set_power_mode("auto")
    else:
        print("Invalid mode. Use 'keyboard' or 'cron'.")


if __name__ == "__main__":
    timestamp_file = getAbsPath("timestamp.txt")
    main()
