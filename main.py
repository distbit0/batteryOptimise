import os
import pwd
import json
import tempfile
import psutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from utils import (
    BatteryStatus,
    ChargeHistory,
    SystemUser,
    StateManager,
    configure_logging,
    getAbsPath,
    read_file,
    execute_command,
)

BATTERY_EXECUTION_MODES = {"onBattery", "onBatteryLidClosed"}


def replace_placeholders(command):
    username, home_directory = SystemUser.get_real_user()
    return command.replace("$$$", getAbsPath("")).replace("~", home_directory)


def execute_commands(commands):
    for command, timeout in commands:
        execute_command(command, timeout)


def read_lid_closed(lid_state_file):
    lid_state = read_file(lid_state_file).split()
    if not lid_state or lid_state[-1].lower() not in {"open", "closed"}:
        raise ValueError(f"Unexpected lid state in {lid_state_file}")
    return lid_state[-1].lower() == "closed"


def read_ac_connected(ac_state_file):
    ac_state = read_file(ac_state_file)
    if ac_state not in {"0", "1"}:
        raise ValueError(f"Unexpected AC state in {ac_state_file}: {ac_state!r}")
    return ac_state == "1"


def select_execution_mode(
    lid_closed, ac_connected, is_on_battery, last_execution_mode
):
    if lid_closed and not ac_connected:
        return "onBatteryLidClosed"
    if ac_connected and last_execution_mode == "onBatteryLidClosed":
        return "onAC"
    return "onBattery" if is_on_battery else "onAC"


def sync_auto_cpufreq_config(source_file, destination_file):
    source_path = Path(source_file)
    destination_path = Path(destination_file)
    source_content = source_path.read_bytes()

    if destination_path.exists() and destination_path.read_bytes() == source_content:
        return False

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination_path.parent,
            prefix=f".{destination_path.name}.",
            delete=False,
        ) as temporary_file:
            temporary_file.write(source_content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        temporary_path.chmod(0o644)
        os.replace(temporary_path, destination_path)
        return True
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def apply_auto_cpufreq_policy(config, current_execution_mode):
    auto_cpufreq_config = config["auto_cpufreq"]
    closed_lid_battery_mode = current_execution_mode == "onBatteryLidClosed"
    profile_name = (
        auto_cpufreq_config["closed_lid_battery_config"]
        if closed_lid_battery_mode
        else auto_cpufreq_config["standard_config"]
    )
    source_file = getAbsPath(profile_name)
    destination_file = auto_cpufreq_config["system_config"]

    if sync_auto_cpufreq_config(source_file, destination_file):
        logging.info(f"Installed auto-cpufreq profile: {profile_name}")
    else:
        logging.info(f"Auto-cpufreq profile already current: {profile_name}")

    governor_override = (
        "powersave"
        if current_execution_mode in BATTERY_EXECUTION_MODES
        else "reset"
    )
    turbo_override = "never" if closed_lid_battery_mode else "auto"
    execute_command(
        f"auto-cpufreq --force={governor_override}",
        timeout=10,
        raise_on_error=True,
    )
    execute_command(
        f"auto-cpufreq --turbo={turbo_override}",
        timeout=10,
        raise_on_error=True,
    )


def should_execute(execution_state, current_execution_mode, config):
    last_execution_mode = execution_state["last_execution_mode"]
    last_execution_time = execution_state.get("last_execution_time")

    min_interval = timedelta(hours=config["min_execution_interval"])
    current_time = datetime.now()
    boot_time = datetime.fromtimestamp(psutil.boot_time())

    time_elapsed = (
        current_time - datetime.fromisoformat(last_execution_time)
        if last_execution_time
        else min_interval
    )

    mode_changed = last_execution_mode != current_execution_mode
    time_elapsed_sufficient = time_elapsed >= min_interval
    system_rebooted = last_execution_time is None or boot_time > datetime.fromisoformat(
        last_execution_time
    )

    should_run = mode_changed or time_elapsed_sufficient or system_rebooted

    if not should_run:
        logging.info(
            f"Last executed {time_elapsed.total_seconds() / 3600:.2f} hours ago. "
            f"Not executing due to insufficient time elapsed."
        )
        return False, current_time, time_elapsed

    if system_rebooted:
        logging.info("System reboot detected. Executing...")
    elif mode_changed:
        logging.info("Execution mode has changed. Executing...")
    else:
        logging.info(
            f"Sufficient time ({time_elapsed.total_seconds() / 3600:.2f} hours) has elapsed. Executing..."
        )

    return True, current_time, time_elapsed


def check_screen_lock_status(regular_user, dbus_address):
    # Check XFCE4 screensaver (most likely on XFCE)
    xfce_command = (
        f"DBUS_SESSION_BUS_ADDRESS={dbus_address} "
        f"gdbus call --session --dest org.xfce.ScreenSaver "
        f"--object-path / "
        f"--method org.xfce.ScreenSaver.GetActive"
    )
    xfce_status = execute_command(f"su -m {regular_user} -c '{xfce_command}'")
    if xfce_status and "true" in xfce_status.lower():
        logging.info(f"Screen is locked (XFCE). Lock status output: {xfce_status}")
        return False

    # Check GNOME screensaver
    gdbus_command = (
        f"DBUS_SESSION_BUS_ADDRESS={dbus_address} "
        f"gdbus call --session --dest org.gnome.ScreenSaver "
        f"--object-path /org/gnome/ScreenSaver "
        f"--method org.gnome.ScreenSaver.GetActive"
    )
    lock_status = execute_command(f"su -m {regular_user} -c '{gdbus_command}'")
    if lock_status and "true" in lock_status.lower():
        logging.info(f"Screen is locked (GNOME). Lock status output: {lock_status}")
        return False

    # Check XScreenSaver
    xscreensaver_command = (
        f"su -m {regular_user} -c 'xscreensaver-command -time 2>/dev/null'"
    )
    xss_status = execute_command(xscreensaver_command)
    if xss_status and "screen locked" in xss_status.lower():
        logging.info(
            f"Screen is locked (XScreenSaver). Lock status output: {xss_status}"
        )
        return False

    # Check X11 DPMS status
    dpms_command = f"su -m {regular_user} -c 'xset q 2>/dev/null | grep \"Monitor is\"'"
    dpms_status = execute_command(dpms_command)
    if dpms_status and any(
        state in dpms_status.lower() for state in ["standby", "suspend", "off"]
    ):
        logging.info(f"Screen is in power saving mode (X11). Status: {dpms_status}")
        return False

    return True


def is_screen_on_and_unlocked():
    username, _ = SystemUser.get_real_user()
    if not username:
        logging.error("Unable to determine the regular user.")
        return False

    try:
        uid = pwd.getpwnam(username).pw_uid
    except KeyError:
        logging.error(f"User '{username}' not found.")
        return False

    dbus_address = f"unix:path=/run/user/{uid}/bus"

    session_status = execute_command(
        f"su -m {username} -c 'loginctl show-session $(loginctl show-user {username} -p Display --value) -p State --value'"
    )

    if "active" not in session_status.lower():
        logging.info(f"Session is not active. Status: {session_status}")
        return False

    unlocked = check_screen_lock_status(username, dbus_address)
    if not unlocked:
        logging.info("Screen is locked. Not executing command.")
        return False

    logging.info("Screen is on and unlocked.")
    return True


def main():
    configure_logging("power_mode")
    logging.info("Starting power mode script")

    with open(getAbsPath("config.json"), "r") as f:
        config = json.load(f)

    state_manager = StateManager(getAbsPath("execution_state.json"))
    execution_state = state_manager.read_state()

    battery = BatteryStatus()
    history = ChargeHistory(getAbsPath("charge_history.log"))

    history.add_entry(battery.get_charge())
    history.save()

    lid_closed = read_lid_closed(config["lid_state_file"])
    ac_connected = read_ac_connected(config["ac_state_file"])
    charge_direction = history.get_charge_direction()
    is_on_battery = (
        charge_direction == -1
        if charge_direction != 0
        else (execution_state["last_execution_mode"] in BATTERY_EXECUTION_MODES)
    )

    current_execution_mode = select_execution_mode(
        lid_closed,
        ac_connected,
        is_on_battery,
        execution_state["last_execution_mode"],
    )
    if current_execution_mode == "onBatteryLidClosed":
        recurring_commands = []
        one_time_commands = []
    else:
        mode_config = config["battery_mode"] if is_on_battery else config["ac_mode"]
        recurring_commands = mode_config["commands"]["recurring"]
        one_time_commands = mode_config["commands"]["oneTime"]

    execute_one_time, current_time, time_elapsed = should_execute(
        execution_state, current_execution_mode, config
    )

    if execute_one_time:
        apply_auto_cpufreq_policy(config, current_execution_mode)
        execute_commands(
            [[replace_placeholders(cmd[0]), cmd[1]] for cmd in one_time_commands]
        )

        execution_state.update(
            {
                "last_execution_mode": current_execution_mode,
                "last_execution_time": current_time.isoformat(),
            }
        )
        state_manager.write_state(execution_state)
        logging.info(f"Executed ALL commands in {current_execution_mode} mode")
    else:
        logging.info(f"Executed recurring commands in {current_execution_mode} mode")

    if recurring_commands and is_screen_on_and_unlocked():
        execute_commands(
            [[replace_placeholders(cmd[0]), cmd[1]] for cmd in recurring_commands]
        )


if __name__ == "__main__":
    if os.geteuid() != 0:
        logging.error("This script must be run as root")
        exit(1)
    main()
