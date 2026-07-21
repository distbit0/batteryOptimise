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

`battery-lid-lock.service` subscribes to systemd-logind's `LidClosed` D-Bus
property and owns the XFCE lock/DPMS actions without polling. It runs throughout
the graphical session; the separate lid-close inhibitor only suppresses logind
poweroff and must release if this monitor fails. The service declares the local
LightDM X11 display and authority file explicitly because the lingering user
manager can start `graphical-session.target` before XFCE imports its environment.
