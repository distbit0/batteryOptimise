echo - | awk "{printf \"%.1f\", $(( $(cat /sys/class/power_supply/BATT/current_now) * $(cat /sys/class/power_supply/BATT/voltage_now) )) / 1000000000000 }"; echo " W"
