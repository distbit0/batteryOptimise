import subprocess
import os

command = "gdbus call --session --dest org.gnome.ScreenSaver --object-path /org/gnome/ScreenSaver --method org.gnome.ScreenSaver.GetActive"
timeout = 10

result = subprocess.run(
    command, shell=True, timeout=timeout, text=True, capture_output=True
)

print(result.stdout)
print(result.stderr)