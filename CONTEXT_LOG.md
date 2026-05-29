# AC Performance Enforcement

- The AC path in `config.json` previously set `tuned-adm profile balanced-battery`, which can hold CPU governor/EPP away from performance even when wall power is connected.
- AC mode now explicitly runs `tlp ac` and sets tuned to `throughput-performance` so both controllers converge on a performance-oriented policy when plugged in.
- `tlp.conf` now pins AC CPU/platform knobs (`CPU_SCALING_GOVERNOR_ON_AC`, `CPU_ENERGY_PERF_POLICY_ON_AC`, `PLATFORM_PROFILE_ON_AC`, `SCHED_POWERSAVE_ON_AC`) to performance-focused values. This avoids relying on distro defaults that may be conservative.

# PowerTOP Shutdown Hang

- May 6 shutdown logs showed two `powertop --auto-tune` runs from the battery policy stuck in uninterruptible kernel sleep; both survived SIGTERM, SIGKILL, and left `/home` busy during final shutdown. Battery mode no longer invokes PowerTOP because it is unsafe on this Lunar Lake/Fedora stack.
- The remaining battery policy still contains TLP/tuned commands, but the current system has no `tlp` binary and `tuned.service` is masked. Treat that as a separate power-policy cleanup; the shutdown fix is to stop scheduling PowerTOP.

# Inactive Power Managers

- `config.json` archives TLP commands instead of executing them because `tlp` is not installed and `tlp.service` is not found on the current system.
- `config.json` archives tuned profile commands instead of executing them because `tuned.service` is masked and inactive. Re-enable tuned deliberately before moving those commands back into active mode policy.
