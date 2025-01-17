import glob
import pysnooper
import os
from datetime import datetime, timedelta

HISTORY_DURATION_MINUTES = 10


def read_file(pattern):
    paths = glob.glob(pattern)
    if not paths:
        raise FileNotFoundError(f"No files found matching: {pattern}")
    with open(paths[0], "r") as f:
        return f.read().strip()


def read_battery_voltage():
    # Typically in microvolts; convert to volts
    try:
        raw_voltage = float(read_file("/sys/class/power_supply/BAT*/voltage_now"))
        return raw_voltage / 1e6
    except FileNotFoundError:
        return 0.0


def read_battery_charge():
    # Typically in microamp-hours
    # If "charge_now" is missing, try "energy_now" (some systems name it differently)
    try:
        return float(read_file("/sys/class/power_supply/BAT*/charge_now"))
    except FileNotFoundError:
        return float(read_file("/sys/class/power_supply/BAT*/energy_now"))


def read_battery_full():
    # Same logic for full capacity
    try:
        return float(read_file("/sys/class/power_supply/BAT*/charge_full"))
    except FileNotFoundError:
        return float(read_file("/sys/class/power_supply/BAT*/energy_full"))


def read_charge_end_threshold():
    # Some systems have a file for charge_control_end_threshold
    try:
        return float(
            read_file("/sys/class/power_supply/BAT*/charge_control_end_threshold")
        )
    except FileNotFoundError:
        return 100.0


def read_ac_status():
    # "1" if AC is online, "0" if offline
    return read_file("/sys/class/power_supply/AC*/online")


def load_charge_history(history_file):
    if not os.path.exists(history_file):
        return []
    cutoff_time = datetime.now() - timedelta(minutes=HISTORY_DURATION_MINUTES)
    entries = []
    with open(history_file, "r") as f:
        for line in f:
            try:
                ts_str, ch_str = line.strip().split(",")
                ts = datetime.fromtimestamp(float(ts_str))
                ch = float(ch_str)
                if ts >= cutoff_time:
                    entries.append((ts, ch))
            except (ValueError, IndexError):
                pass
    return entries


def save_charge_history(entries, history_file):
    with open(history_file, "w") as f:
        for ts, ch in entries:
            f.write(f"{ts.timestamp()},{ch}\n")


def get_charge_direction(history_entries):
    if len(history_entries) < 2:
        return 0
    _, prev_charge = history_entries[-2]
    _, last_charge = history_entries[-1]
    if last_charge > prev_charge:
        return 1
    elif last_charge < prev_charge:
        return -1
    return 0


def delta_power_watts(charge_diff_microah, hours_diff, voltage):
    # charge_diff_microah is ΔQ in microamp-hours
    # convert ΔQ to amp-hours (divide by 1e6), then multiply by voltage
    # Power = voltage * (ΔQ / Δt)
    if hours_diff == 0 or voltage == 0:
        return 0.0
    return voltage * ((charge_diff_microah / 1e6) / hours_diff)


def calculate_now_power(history_entries, voltage):
    # Use last three readings for smoother measurement
    if len(history_entries) < 3:
        return 0.0
    
    # Get last three samples
    t1, c1 = history_entries[-3]
    t2, c2 = history_entries[-2]
    t3, c3 = history_entries[-1]
    
    # Calculate power between each pair
    hours_diff1 = (t2 - t1).total_seconds() / 3600
    charge_diff1 = c2 - c1
    power1 = delta_power_watts(charge_diff1, hours_diff1, voltage)
    
    hours_diff2 = (t3 - t2).total_seconds() / 3600
    charge_diff2 = c3 - c2
    power2 = delta_power_watts(charge_diff2, hours_diff2, voltage)
    
    # Return average of the two measurements
    return (power1 + power2) / 2


@pysnooper.snoop()
def calculate_avg_power(history_entries, voltage):
    # Compare the very first and the very last in the (up to 10-minute) window
    if len(history_entries) < 2:
        return 0.0
    t_first, c_first = history_entries[0]
    t_last, c_last = history_entries[-1]
    hours_diff = (t_last - t_first).total_seconds() / 3600
    charge_diff = c_last - c_first
    return delta_power_watts(charge_diff, hours_diff, voltage)


def calculate_time_remaining(current_charge, total_capacity, avg_power_watts, voltage):
    # Convert power to current in microamps: I (A) = P / V, multiply by 1e6 for microamps
    if avg_power_watts == 0 or voltage == 0:
        return float("inf")
    avg_current_uA = (avg_power_watts / voltage) * 1e6
    if avg_power_watts > 0:
        # Battery is charging
        return (total_capacity - current_charge) / abs(avg_current_uA)
    # Battery is discharging
    return current_charge / abs(avg_current_uA)


def main():
    voltage_now = read_battery_voltage()
    current_charge = read_battery_charge()
    charge_full = read_battery_full()
    end_threshold = read_charge_end_threshold()
    ac_state = read_ac_status()

    total_capacity = (end_threshold * charge_full) / 100.0

    # Load or create history
    script_dir = os.path.dirname(os.path.realpath(__file__))
    log_file = os.path.join(script_dir, "charge_history.log")
    history_entries = load_charge_history(log_file)

    # Check for direction changes
    new_direction = 1 if ac_state == "1" else -1
    if history_entries:
        old_direction = get_charge_direction(history_entries)
        if old_direction != 0 and old_direction != new_direction:
            history_entries.clear()

    # Update history
    now_ts = datetime.now()
    history_entries.append((now_ts, current_charge))
    # Retain only entries within the last HISTORY_DURATION_MINUTES
    history_entries = [
        (ts, ch)
        for ts, ch in history_entries
        if (now_ts - ts) <= timedelta(minutes=HISTORY_DURATION_MINUTES)
    ]
    save_charge_history(history_entries, log_file)

    # Calculate power
    now_power = calculate_now_power(history_entries, voltage_now)
    avg_power = calculate_avg_power(history_entries, voltage_now)

    # Calculate time remaining
    hours_remaining = calculate_time_remaining(
        current_charge, total_capacity, avg_power, voltage_now
    )
    hours_remaining_rounded = abs(round(hours_remaining, 1))
    if hours_remaining_rounded > 40:
        hours_remaining_rounded = float("inf")

    # Battery percentage
    battery_pct = int((current_charge / charge_full) * 100)

    print(
        f"| {battery_pct}% | NOW: {round(now_power, 1)}W || "
        f"AVG: {round(avg_power, 1)}W | {hours_remaining_rounded}H |"
    )


if __name__ == "__main__":
    main()
