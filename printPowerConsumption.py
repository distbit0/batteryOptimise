import glob
import time
import os
from datetime import datetime, timedelta

def load_power_history(log_file):
    """Load and clean power consumption history from log file"""
    if not os.path.exists(log_file):
        return []
    
    current_time = datetime.now()
    history = []
    
    with open(log_file, 'r') as f:
        for line in f.readlines():
            try:
                timestamp_str, power_str = line.strip().split(',')
                timestamp = datetime.fromtimestamp(float(timestamp_str))
                if current_time - timestamp <= timedelta(minutes=10):
                    history.append((timestamp, float(power_str)))
            except (ValueError, IndexError):
                continue
    
    return history

def save_power_history(history, log_file):
    """Save power consumption history to log file"""
    with open(log_file, 'w') as f:
        for timestamp, power in history:
            f.write(f"{timestamp.timestamp()},{power}\n")

def calculate_average_power(history):
    """Calculate average power consumption from history"""
    if not history:
        return 0.0
    return sum(power for _, power in history) / len(history)

def read_file(path):
    matching_files = glob.glob(path)
    if not matching_files:
        raise FileNotFoundError(f"No files found matching the pattern: {path}")

    # Use the first matching file
    file_path = matching_files[0]
    with open(file_path, "r") as file:
        return file.read().strip()


# Read AC status, current (in microamperes), and voltage (in microvolts)
ac_status = read_file("/sys/class/power_supply/AC*/online")
current_now = float(read_file("/sys/class/power_supply/BAT*/current_now"))
voltage_now = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))

# Calculate power consumption in watts
power_consumption = current_now * voltage_now / 10**12

# Adjust sign based on AC status
if ac_status == "0":
    power_consumption = -power_consumption
elif ac_status == "1":
    power_consumption = +power_consumption

# Read battery's current charge and total capacity (in microamperes-hours)
current_charge = float(read_file("/sys/class/power_supply/BAT*/charge_now"))
total_capacity = (
    float(read_file("/sys/class/power_supply/BAT*/charge_control_end_threshold"))
    * float(read_file("/sys/class/power_supply/BAT*/charge_full"))
    / 100
)

if power_consumption != 0:
    if power_consumption > 0:
        time_remaining = (total_capacity - current_charge) / current_now
    else:
        time_remaining = current_charge / current_now
else:
    time_remaining = float("inf")  # Represents an infinite amount of time

# Round both values to one decimal place
power_consumption_rounded = round(power_consumption, 1)
time_remaining_rounded = round(time_remaining, 1)
if time_remaining_rounded > 20:
    time_remaining_rounded = float("inf")

# Load and update power consumption history
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "power_history.log")
history = load_power_history(log_file)
history.append((datetime.now(), power_consumption))
history = [x for x in history if datetime.now() - x[0] <= timedelta(minutes=10)]
save_power_history(history, log_file)

# Calculate 10-minute average
avg_power_consumption = calculate_average_power(history)
avg_power_consumption_rounded = round(avg_power_consumption, 1)

print(f"Current: {power_consumption_rounded} W | Avg(10min): {avg_power_consumption_rounded} W | Time: {time_remaining_rounded} H")
