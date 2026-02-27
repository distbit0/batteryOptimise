# AC Performance Enforcement

- The AC path in `config.json` previously set `tuned-adm profile balanced-battery`, which can hold CPU governor/EPP away from performance even when wall power is connected.
- AC mode now explicitly runs `tlp ac` and sets tuned to `throughput-performance` so both controllers converge on a performance-oriented policy when plugged in.
- `tlp.conf` now pins AC CPU/platform knobs (`CPU_SCALING_GOVERNOR_ON_AC`, `CPU_ENERGY_PERF_POLICY_ON_AC`, `PLATFORM_PROFILE_ON_AC`, `SCHED_POWERSAVE_ON_AC`) to performance-focused values. This avoids relying on distro defaults that may be conservative.
