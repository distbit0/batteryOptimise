import glob
import time
import os
from datetime import datetime, timedelta

def load_charge_history(log_file):
    """Load and clean battery charge history from log file"""
    if not os.path.exists(log_file):
        return []
    
    current_time = datetime.now()
    history = []
    
    with open(log_file, 'r') as f:
        for line in f.readlines():
            try:
                timestamp_str, charge_str = line.strip().split(',')
                timestamp = datetime.fromtimestamp(float(timestamp_str))
                charge = float(charge_str)
                if current_time - timestamp <= timedelta(minutes=10):
                    history.append((timestamp, charge))
            except (ValueError, IndexError):
                continue
    
    return history

def save_charge_history(history, log_file):
    """Save battery charge history to log file"""
    with open(log_file, 'w') as f:
        for timestamp, charge in history:
            f.write(f"{timestamp.timestamp()},{charge}\n")

def calculate_average_power(history, current_charge, voltage_now):
    """Calculate average power consumption from charge history"""
    if len(history) < 2:
        return 0.0
    
    # Get the oldest and newest entries
    oldest = history[0]
    newest = (datetime.now(), current_charge)
    
    # Calculate time difference in hours
    time_diff = (newest[0] - oldest[0]).total_seconds() / 3600
    
    # Calculate charge difference in Ah (microamperes-hours to amperes-hours)
    charge_diff = (newest[1] - oldest[1]) / 10**6
    
    # Power = Voltage * Current = Voltage * (ΔCharge/ΔTime)
    return voltage_now * (charge_diff / time_diff) / 10**6

def read_file(path):
    matching_files = glob.glob(path)
    if not matching_files:
        raise FileNotFoundError(f"No files found matching the pattern: {path}")

    # Use the first matching file
    file_path = matching_files[0]
    with open(file_path, "r") as file:
        return file.read().strip()


# current (in microamperes), and voltage (in microvolts)
voltage_now = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))
try:
    try:
        current_now = float(read_file("/sys/class/power_supply/BAT*/current_now"))
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
try:
    current_charge = float(read_file("/sys/class/power_supply/BAT*/charge_now"))
except:
    current_charge  = float(read_file("/sys/class/power_supply/BAT*/energy_now"))
try:
    charge_full = float(read_file("/sys/class/power_supply/BAT*/charge_full"))
except:
    charge_full = float(read_file("/sys/class/power_supply/BAT*/energy_full"))
total_capacity = (
    float(read_file("/sys/class/power_supply/BAT*/charge_control_end_threshold"))
    * charge_full
    / 100
)

# Round power consumption
power_consumption_rounded = round(power_consumption, 1)

# Load and update charge history
log_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "charge_history.log")
history = load_charge_history(log_file)
history.append((datetime.now(), current_charge))
history = [x for x in history if datetime.now() - x[0] <= timedelta(minutes=10)]
save_charge_history(history, log_file)

# Calculate 10-minute average power consumption
avg_power_consumption = calculate_average_power(history, current_charge, voltage_now)
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