import sys
import subprocess
from datetime import datetime, timedelta
from os import path
import tkinter as tk
from tkinter import font as tkFont


def show_notification_for_one_second(message):
    root = tk.Tk()
    # Set the window title
    root.title("Notification")

    # Create a label with the provided text
    large_font = tkFont.Font(family="Helvetica", size=30)

    # Create a label with the provided text using the large font
    label = tk.Label(root, text=message, font=large_font)
    label.pack()

    # Update the window size and position
    root.update_idletasks()  # Update the window's internal data
    window_width = root.winfo_width()
    window_height = root.winfo_height()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width - window_width) / 2)
    y = int((screen_height - window_height) / 2)
    root.geometry(f"+{x}+{y}")  # Set the window position

    # Schedule the window to close after 1000 milliseconds (1 second)
    root.after(1000, root.destroy)

    # Run the main loop to display the window
    root.mainloop()


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
    """
    try:
        with open(timestamp_file, "r") as file:
            saved_time = datetime.strptime(file.read().strip(), "%Y-%m-%d %H:%M:%S")
            return datetime.now() > saved_time
    except FileNotFoundError:
        return False  # No timestamp file found, default to False


def main():
    if len(sys.argv) != 2:
        print("Usage: script.py [keyboard|cron]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "keyboard":
        if not is_past_timestamp():
            show_notification_for_one_second("AUTO")
            set_power_mode("auto")
            save_relative_timestamp(-3)
        else:
            show_notification_for_one_second("BAT")
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
