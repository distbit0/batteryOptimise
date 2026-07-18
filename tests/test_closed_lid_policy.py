import asyncio
import configparser
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from main import (
    BATTERY_EXECUTION_MODES,
    parse_arguments,
    read_ac_connected,
    read_lid_closed,
    read_logind_lid_closed,
    select_execution_mode,
    should_execute,
    sync_auto_cpufreq_config,
)


PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]


class ClosedLidPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((PROJECT_DIRECTORY / "config.json").read_text())

    def test_strict_mode_requires_closed_lid_and_disconnected_ac(self):
        self.assertEqual(
            select_execution_mode(
                lid_closed=True,
                ac_connected=False,
                is_on_battery=True,
                last_execution_mode="onBattery",
            ),
            "onBatteryLidClosed",
        )
        self.assertEqual(
            select_execution_mode(
                lid_closed=False,
                ac_connected=False,
                is_on_battery=True,
                last_execution_mode="onBatteryLidClosed",
            ),
            "onBattery",
        )
        self.assertEqual(
            select_execution_mode(
                lid_closed=True,
                ac_connected=True,
                is_on_battery=False,
                last_execution_mode="onAC",
            ),
            "onAC",
        )
        self.assertEqual(
            select_execution_mode(
                lid_closed=False,
                ac_connected=True,
                is_on_battery=False,
                last_execution_mode="onAC",
            ),
            "onAC",
        )

    def test_connecting_ac_exits_strict_mode_despite_flat_charge_history(self):
        self.assertEqual(
            select_execution_mode(
                lid_closed=True,
                ac_connected=True,
                is_on_battery=True,
                last_execution_mode="onBatteryLidClosed",
            ),
            "onAC",
        )

    def test_closed_lid_mode_remains_a_battery_execution_mode(self):
        self.assertIn("onBatteryLidClosed", BATTERY_EXECUTION_MODES)

    def test_entering_strict_mode_bypasses_the_refresh_interval(self):
        execution_state = {
            "last_execution_mode": "onBattery",
            "last_execution_time": datetime.now().isoformat(),
        }
        should_run, _, _ = should_execute(
            execution_state,
            "onBatteryLidClosed",
            self.config,
        )
        self.assertTrue(should_run)

    def test_reads_current_hardware_states(self):
        lid_state_file = self.config["lid_state_file"]
        ac_state_file = self.config["ac_state_file"]

        self.assertEqual(
            read_lid_closed(lid_state_file),
            Path(lid_state_file).read_text().split()[-1].lower() == "closed",
        )
        self.assertEqual(
            read_ac_connected(ac_state_file),
            next(Path("/sys/class/power_supply").glob("AC*/online")).read_text().strip()
            == "1",
        )

    def test_lid_monitor_service_uses_monitor_command(self):
        service = configparser.ConfigParser(interpolation=None)
        service.read(PROJECT_DIRECTORY / "battery-lid-lock.service")
        exec_start = service["Service"]["ExecStart"].split()

        self.assertEqual(parse_arguments(exec_start[-1:]).command, "monitor-lid")
        self.assertEqual(service["Service"]["Restart"], "on-failure")

    def test_logind_lid_state_matches_current_hardware_state(self):
        self.assertEqual(
            asyncio.run(read_logind_lid_closed()),
            read_lid_closed(self.config["lid_state_file"]),
        )

    def test_rejects_real_non_state_file_contents(self):
        config_file = str(PROJECT_DIRECTORY / "config.json")
        with self.assertRaises(ValueError):
            read_lid_closed(config_file)
        with self.assertRaises(ValueError):
            read_ac_connected(config_file)

    def test_closed_lid_profile_uses_lowest_energy_settings(self):
        profile = configparser.ConfigParser()
        profile.read(
            PROJECT_DIRECTORY
            / self.config["auto_cpufreq"]["closed_lid_battery_config"]
        )
        expected_settings = {
            "governor": "powersave",
            "energy_performance_preference": "power",
            "energy_perf_bias": "power",
            "platform_profile": "quiet",
            "turbo": "never",
        }

        for power_source in ("charger", "battery"):
            self.assertEqual(dict(profile[power_source]), expected_settings)

    def test_syncs_real_profiles_atomically_only_when_changed(self):
        standard_profile = (
            PROJECT_DIRECTORY / self.config["auto_cpufreq"]["standard_config"]
        )
        closed_lid_profile = (
            PROJECT_DIRECTORY
            / self.config["auto_cpufreq"]["closed_lid_battery_config"]
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "auto-cpufreq.conf"
            destination.write_bytes(standard_profile.read_bytes())

            self.assertFalse(
                sync_auto_cpufreq_config(standard_profile, destination)
            )
            self.assertTrue(
                sync_auto_cpufreq_config(closed_lid_profile, destination)
            )
            self.assertEqual(destination.read_bytes(), closed_lid_profile.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
