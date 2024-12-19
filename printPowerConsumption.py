import glob
import time
import os
from datetime import datetime, timedelta

def load_power_history(log_file, current_power):
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
                power = float(power_str)
                # Only include entries that have the same sign as current power
                if (current_time - timestamp <= timedelta(minutes=10) and 
                    ((current_power >= 0 and power >= 0) or 
                     (current_power < 0 and power < 0))):
                    history.append((timestamp, power))
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


# current (in microamperes), and voltage (in microvolts)
try:
    try:
        current_now = float(read_file("/sys/class/power_supply/BAT*/current_now"))
        voltage_now = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))
        power_consumption = current_now * voltage_now / 10**12
    except:
        power_consumption = float(read_file("/sys/class/power_supply/BAT*/power_now")) / 10**6
except:
    power_consumption = 0.0

# Adjust sign based on AC status
ac_status = read_file("/sys/class/power_supply/AC*/online")
if ac_status == "0":
    power_consumption = -power_consumption
elif ac_status == "1":
    power_consumption = +power_consumption

# Read battery's current charge and total capacity (in microamperes-hours)
current_charge = float(read_file("/sys/class/power_supply/BAT*/charge_now"))
charge_full = float(read_file("/sys/class/power_supply/BAT*/charge_full"))
total_capacity = (
    float(read_file("/sys/class/power_supply/BAT*/charge_control_end_threshold"))
    * charge_full
    / 100
)

# Round power consumption
power_consumption_rounded = round(power_consumption, 1)

# Load and update power consumption history
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "power_history.log")
history = load_power_history(log_file, power_consumption)
history.append((datetime.now(), power_consumption))
history = [x for x in history if datetime.now() - x[0] <= timedelta(minutes=10)]
save_power_history(history, log_file)

# Calculate 10-minute average
avg_power_consumption = calculate_average_power(history)
avg_power_consumption_rounded = round(avg_power_consumption, 1)

# Calculate time remaining based on average power consumption
if avg_power_consumption != 0:
    avg_current = (avg_power_consumption * 10**12) / voltage_now  # Convert back to microamps
    if avg_power_consumption > 0:
        time_remaining = (total_capacity - current_charge) / abs(avg_current)
    else:
        time_remaining = current_charge / abs(avg_current)
else:
    time_remaining = float("inf")  # Represents an infinite amount of time

time_remaining_rounded = abs(round(time_remaining, 1))
if time_remaining_rounded > 40:
    time_remaining_rounded = float("inf")

battery_percent = int((current_charge / charge_full) * 100)
print(f"| {battery_percent}% | NOW: {power_consumption_rounded}W || AVG: {avg_power_consumption_rounded}W | {time_remaining_rounded}H |")
