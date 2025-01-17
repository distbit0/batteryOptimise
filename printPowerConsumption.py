import os
from utils import BatteryStatus, ChargeHistory, getAbsPath


def main():
    battery = BatteryStatus()

    voltage = battery.get_voltage()
    current_charge = battery.get_charge()
    charge_full = battery.get_full_capacity()
    end_threshold = battery.get_end_threshold()

    total_capacity = (end_threshold * charge_full) / 100.0

    history = ChargeHistory(getAbsPath("charge_history.log"))
    history.add_entry(current_charge)
    history.save()

    now_power, avg_power = history.calculate_power_metrics(voltage)

    if avg_power != 0 and voltage != 0:
        avg_current_ua = (avg_power / voltage) * 1e6
        if avg_power > 0:
            hours_remaining = (total_capacity - current_charge) / abs(avg_current_ua)
        else:
            hours_remaining = current_charge / abs(avg_current_ua)
    else:
        hours_remaining = float("inf")

    hours_remaining_rounded = abs(round(hours_remaining, 1))
    if hours_remaining_rounded > 40:
        hours_remaining_rounded = float("inf")

    battery_pct = battery.get_percentage()

    print(
        f"| {battery_pct}% | NOW: {round(now_power, 1)}W || "
        f"AVG: {round(avg_power, 1)}W | {hours_remaining_rounded}H |"
    )


if __name__ == "__main__":
    main()
