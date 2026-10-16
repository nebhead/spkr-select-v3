#!/usr/bin/env bash

set -Eeuo pipefail

# Speaker-Select-V3 Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/spkr-select-v3/master/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# bash <(wget -O - https://raw.githubusercontent.com/nebhead/spkr-select-v3/master/auto-install/install.sh)

SUDO=""
SUDO_KEEPALIVE_PID=""
TMP_CONTROL_CONF=""
TMP_WEBAPP_CONF=""
TMP_SUDOERS_CONF=""

INSTALL_USER="${SUDO_USER:-${USER}}"
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
INSTALL_HOME="${INSTALL_HOME:-$HOME}"
INSTALL_GROUP="spkrselect"
INSTALL_DIR="/usr/local/bin/spkr-select-v3"
LOG_FILE="$INSTALL_HOME/spkr-select-install-$(date +%Y%m%d-%H%M%S).log"

log_command() {
    echo
    echo "[COMMAND] $*"
    set +e
    "$@" 2>&1 | tee -a "$LOG_FILE"
    local rc=${PIPESTATUS[0]}
    set -e
    if [[ $rc -ne 0 ]]; then
        log_note "ERROR: Command failed with exit code ${rc}: $*"
    fi
    return $rc
}

log_note() {
    echo "$*" | tee -a "$LOG_FILE"
}

on_error() {
    local exit_code="$?"
    local line_no="$1"
    local failed_command="$2"

    log_note "ERROR: Command failed with exit code ${exit_code} at line ${line_no}: ${failed_command}"
    log_note "Installation aborted. Review installer log: ${LOG_FILE}"
    exit "${exit_code}"
}

banner() {
    log_note "*************************************************************************"
    log_note "**                                                                     **"
    log_note "**      $1"
    log_note "**                                                                     **"
    log_note "*************************************************************************"
}

cleanup() {
    if [[ -n "$SUDO_KEEPALIVE_PID" ]]; then
        kill "$SUDO_KEEPALIVE_PID" >/dev/null 2>&1 || true
    fi
    if [[ -n "$TMP_CONTROL_CONF" && -f "$TMP_CONTROL_CONF" ]]; then
        rm -f "$TMP_CONTROL_CONF"
    fi
    if [[ -n "$TMP_WEBAPP_CONF" && -f "$TMP_WEBAPP_CONF" ]]; then
        rm -f "$TMP_WEBAPP_CONF"
    fi
    if [[ -n "$TMP_SUDOERS_CONF" && -f "$TMP_SUDOERS_CONF" ]]; then
        rm -f "$TMP_SUDOERS_CONF"
    fi
}

trap 'on_error "$LINENO" "$BASH_COMMAND"' ERR
trap cleanup EXIT

log_note "Installer log: $LOG_FILE"
log_note "Started: $(date '+%Y-%m-%d %H:%M:%S %Z')"

# Must be root to install
if [[ $EUID -eq 0 ]]; then
    log_note "You are root."
else
    log_note "SUDO will be used for the install."
    if command -v sudo >/dev/null 2>&1; then
        export SUDO="sudo"
    else
        log_note "Please install sudo."
        exit 1
    fi

    # Authenticate once up front, then refresh sudo timestamp while installer runs.
    log_note "*************************************************************************"
    log_note "Please enter your sudo password to continue installation."
    log_note "*************************************************************************"
    sudo -v || { log_note "Failed to authenticate with sudo."; exit 1; }
    while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
    SUDO_KEEPALIVE_PID=$!
fi

# Find the rows and columns. Will default to 80x24 if it can not be detected.
screen_size=$(stty size 2>/dev/null || echo 24 80)
rows=$(echo $screen_size | awk '{print $1}')
columns=$(echo $screen_size | awk '{print $2}')

# Divide by two so the dialogs take up half of the screen.
r=$(( rows / 2 ))
c=$(( columns / 2 ))
# If the screen is small, modify defaults
r=$(( r < 20 ? 20 : r ))
c=$(( c < 70 ? 70 : c ))

# Display the welcome dialog
whiptail --msgbox --backtitle "Welcome" --title "Speaker-Select Automated Installer" "This installer will transform your Raspberry Pi into a smart speaker-selector.  NOTE: This installer is intended to be run on a fresh install of Raspberry Pi OS (Buster) or later." ${r} ${c}

# Starting actual steps for installation
banner "Running Apt Update... (This could take several minutes)"
log_command $SUDO apt update
banner "Running Apt Upgrade... (This could take several minutes)"
log_command $SUDO apt upgrade -y

# Install dependencies
banner "Installing Dependencies... (This could take several minutes)"
log_command $SUDO apt install python3-dev python3-pip python3-venv nginx git supervisor ir-keytable redis-server -y

if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
    log_note "Raspberry Pi 5 detected. Installing python3-rpi-lgpio."
    log_command $SUDO apt install python3-rpi-lgpio -y
else
    log_command $SUDO apt install python3-rpi.gpio -y
fi

# Grab project files
banner "Cloning Speaker-Select from GitHub..."
cd /usr/local/bin
if [[ -d "$INSTALL_DIR" ]]; then
    log_note "Existing ${INSTALL_DIR} directory found."
    log_note "Please remove or rename it before running this installer."
    exit 1
fi
log_command $SUDO git clone https://github.com/nebhead/spkr-select-v3

### Setup Python VENV and Install Python dependencies
banner "Setting up Python VENV and installing modules..."
log_command $SUDO python3 -m venv --system-site-packages ${INSTALL_DIR}/.venv
log_command $SUDO ${INSTALL_DIR}/.venv/bin/pip install --upgrade pip
log_command $SUDO ${INSTALL_DIR}/.venv/bin/pip install -r ${INSTALL_DIR}/auto-install/requirements.txt

### Configure project ownership and permissions for supervisor-managed processes
banner "Configuring Project Ownership and Permissions..."
if getent group "$INSTALL_GROUP" >/dev/null 2>&1; then
    log_note "Group ${INSTALL_GROUP} already exists."
else
    log_command $SUDO groupadd "$INSTALL_GROUP"
fi
log_command $SUDO usermod -a -G "$INSTALL_GROUP" "$INSTALL_USER"
log_command $SUDO usermod -a -G "$INSTALL_GROUP" root
log_command $SUDO mkdir -p "${INSTALL_DIR}/logs"
log_command $SUDO chown -R "${INSTALL_USER}:${INSTALL_GROUP}" "$INSTALL_DIR"
log_command $SUDO chmod -R g+rwX "$INSTALL_DIR"
log_command $SUDO find "$INSTALL_DIR" -type d -exec chmod g+s {} +
log_note "Applied group-based permissions to ${INSTALL_DIR} for user ${INSTALL_USER}."

### Configure limited sudo permissions for power actions from web UI
banner "Configuring Limited Sudo Permissions for Reboot/Shutdown..."
REBOOT_BIN="$(command -v reboot || true)"
SHUTDOWN_BIN="$(command -v shutdown || true)"

if [[ -z "$REBOOT_BIN" || -z "$SHUTDOWN_BIN" ]]; then
    log_note "ERROR: Could not locate reboot/shutdown binaries for sudoers configuration."
    exit 1
fi

TMP_SUDOERS_CONF=$(mktemp)
printf "%s ALL=(root) NOPASSWD: %s, %s\n" "$INSTALL_USER" "$REBOOT_BIN" "$SHUTDOWN_BIN" > "$TMP_SUDOERS_CONF"
if ! log_command $SUDO visudo -cf "$TMP_SUDOERS_CONF"; then
    log_note "ERROR: Generated sudoers file failed validation."
    exit 1
fi
log_command $SUDO install -m 0440 "$TMP_SUDOERS_CONF" /etc/sudoers.d/spkr-select
log_command $SUDO visudo -cf /etc/sudoers.d/spkr-select
log_note "Installed sudoers drop-in for ${INSTALL_USER}: ${REBOOT_BIN}, ${SHUTDOWN_BIN}"

### Setup nginx to proxy to gunicorn
banner "Configuring nginx..."
# Move into install directory
cd ${INSTALL_DIR}/auto-install/nginx

# Delete default configuration
if [[ -e /etc/nginx/sites-enabled/default ]]; then
    log_command $SUDO rm /etc/nginx/sites-enabled/default
else
    log_note "Default nginx site already removed."
fi

# Copy configuration file to nginx
log_command $SUDO cp spkr-select.nginx /etc/nginx/sites-available/spkr-select

# Create link in sites-enabled
if [[ -L /etc/nginx/sites-enabled/spkr-select || -e /etc/nginx/sites-enabled/spkr-select ]]; then
    log_note "nginx site link already exists."
else
    log_command $SUDO ln -s /etc/nginx/sites-available/spkr-select /etc/nginx/sites-enabled/spkr-select
fi

# Generate self-signed SSL certificate (non-interactive)
banner "Generating Self-Signed SSL Certificate..."
if ! log_command $SUDO openssl req -x509 -nodes -days 3650 -newkey rsa:2048 -keyout /etc/ssl/private/localhost.key -out /etc/ssl/certs/localhost.crt -subj "/CN=localhost" -batch; then
    log_note "WARNING: Failed to generate SSL certificate. HTTPS may not function correctly."
else
    log_note "SSL certificate generation successful."
fi

# Restart nginx
log_command $SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
banner "Configuring Supervisord..."

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for the installation then make sure you edit the *.conf files appropriately
cd ${INSTALL_DIR}/auto-install/supervisor
TMP_CONTROL_CONF=$(mktemp)
TMP_WEBAPP_CONF=$(mktemp)
sed "s/__INSTALL_USER__/${INSTALL_USER}/g" control.conf > "$TMP_CONTROL_CONF"
sed "s/__INSTALL_USER__/${INSTALL_USER}/g" webapp.conf > "$TMP_WEBAPP_CONF"
log_command $SUDO cp "$TMP_CONTROL_CONF" /etc/supervisor/conf.d/control.conf
log_command $SUDO cp "$TMP_WEBAPP_CONF" /etc/supervisor/conf.d/webapp.conf

SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
    echo " " | $SUDO tee -a /etc/supervisor/supervisord.conf > /dev/null
    echo "[inet_http_server]" | $SUDO tee -a /etc/supervisor/supervisord.conf > /dev/null
    echo "port = 9001" | $SUDO tee -a /etc/supervisor/supervisord.conf > /dev/null
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
    echo "username = ${USERNAME}" | $SUDO tee -a /etc/supervisor/supervisord.conf > /dev/null
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
    echo "password = ${PASSWORD}" | $SUDO tee -a /etc/supervisor/supervisord.conf > /dev/null
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Setup Completed" "You now should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
    log_note "No WebUI Setup."
fi

# If supervisor isn't already running, startup Supervisor
log_command $SUDO service supervisor start

# Check if the user would like to install IR support.  
if (whiptail --title "Setup IR Support" --yesno "Do you want to setup IR support?" 8 78); then
	if grep -Fxq "dtoverlay=gpio-ir,gpio_pin=27" /boot/config.txt 
	then
        log_note "/boot/config.txt already setup with GPIO pin 27, skipping step."
	else
        log_note "Adding GPIO Pin 27, IR Support to the /boot/config.txt file..."
        log_command $SUDO tee -a /boot/config.txt > /dev/null <<<'dtoverlay=gpio-ir,gpio_pin=27'
	fi
	# Let the user know that the installation needs to be completed after a reboot
	whiptail --msgbox --backtitle "Install Almost Complete / Reboot Required" --title "Reboot" "Congratulations, the installation is almost complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  To continue to setup the IR Remote capability after the reboot, ssh into the pi again and run 'bash /usr/local/bin/spkr-select-v3/auto-install/setup_ir.sh'.  This should walk through the steps to complete your setup." ${r} ${c}
else
    log_note "Skipping IR Setup."
	whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  Enjoy!" ${r} ${c}
fi

# Rebooting
log_note "Rebooting now."
log_command $SUDO reboot
