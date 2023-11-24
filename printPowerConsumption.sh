#!/bin/bash

ac_status=$(cat /sys/class/power_supply/ACAD/online)
echo $ac_status
power_consumption=$(echo "scale=1; $(cat /sys/class/power_supply/BATT/current_now) * $(cat /sys/class/power_supply/BATT/voltage_now) / 1000000000000" | bc)
if [ "$ac_status" -eq 0 ]; then
    power_consumption="-$power_consumption"
fi

echo "$power_consumption W"
