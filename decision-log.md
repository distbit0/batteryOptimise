# Decision Log

## One active power-policy owner

`auto-cpufreq` is the active power manager. TLP is not installed and TuneD is
masked, so their commands remain archived in configuration and must not be
reactivated without deliberately changing ownership of the power policy.

## Do not run PowerTOP auto-tune

PowerTOP auto-tune is unsafe on this Lunar Lake Fedora system: observed runs
became stuck in uninterruptible kernel sleep and prevented clean shutdown. Keep
it out of both AC and battery policy.
