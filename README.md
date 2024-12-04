non-python dependencies:

sudo dnf install tlp tlp-rdw powertop

curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/AdnanHodzic/auto-cpufreq.git
cd auto-cpufreq && sudo ./auto-cpufreq-installer

sudo dnf remove tuned tuned-ppd