# Decision Log

## One active power-policy owner

`auto-cpufreq` is the active power manager. TLP is not installed and TuneD is
masked, so their commands remain archived in configuration and must not be
reactivated without deliberately changing ownership of the power policy.

## Do not run PowerTOP auto-tune

PowerTOP auto-tune is unsafe on this Lunar Lake Fedora system: observed runs
became stuck in uninterruptible kernel sleep and prevented clean shutdown. Keep
it out of both AC and battery policy.

## Lid-close desktop lock ownership

`battery-lid-lock.service` owns lid-state monitoring and the XFCE lock/DPMS
actions. It runs throughout the graphical session; the separate lid-close
inhibitor only suppresses logind poweroff and must release if this monitor fails.
