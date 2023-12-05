def read_file(path):
    with open(path, "r") as file:
        return file.read().strip()


# Read AC status, current (in microamperes), and voltage (in microvolts)
ac_status = read_file("/sys/class/power_supply/ACAD/online")
current_now = float(read_file("/sys/class/power_supply/BATT/current_now"))
voltage_now = float(read_file("/sys/class/power_supply/BATT/voltage_now"))

# Calculate power consumption in watts
power_consumption = current_now * voltage_now / 10**12

# Adjust sign based on AC status
if ac_status == "0":
    power_consumption = -power_consumption
elif ac_status == "1":
    power_consumption = +power_consumption

# Read battery's current charge and total capacity (in microamperes-hours)
current_charge = float(read_file("/sys/class/power_supply/BATT/charge_now"))
total_capacity = float(read_file("/sys/class/power_supply/BATT/charge_full"))

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

print(f"{power_consumption_rounded} W | {time_remaining_rounded} H")
