#!/usr/bin/env bash

# Speaker-Select Installation Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script
# Run from https://raw.githubusercontent.com/nebhead/spkr-select/master/auto-install/install.sh
#
# Install with this command (from your Pi):
#
# curl https://raw.githubusercontent.com/nebhead/spkr-select/master/auto-install/install.sh | bash
#
# WARNING: Do NOT run with SUDO or the cd commands will not work properly (i.e. they will use root
# instead of the pi user).  This command will automatically get SUDO and use in the proper places.

# Must be root to install
if [[ $EUID -eq 0 ]];then
    echo "You are root."
else
    echo "SUDO will be used for the install."
    # Check if it is actually installed
    # If it isn't, exit because the install cannot complete
    if [[ $(dpkg-query -s sudo) ]];then
        export SUDO="sudo"
        export SUDOE="sudo -E"
    else
        echo "Please install sudo."
        exit 1
    fi
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
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Update... (This could take several minutes)        **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt update
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Running Apt Upgrade... (This could take several minutes)       **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt upgrade -y

# Install dependancies
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Installing Dependancies... (This could take several minutes)   **"
echo "**                                                                     **"
echo "*************************************************************************"
$SUDO apt install python3-dev python3-pip nginx git gunicorn supervisor ir-keytable redis-server -y
$SUDO pip3 install flask evdev redis gpiozero geopy suntime

# Grab project files
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Cloning Speaker-Select from GitHub...                          **"
echo "**                                                                     **"
echo "*************************************************************************"
cd /usr/local/bin
$SUDO git clone https://github.com/nebhead/spkr-select-v3

### Setup nginx to proxy to gunicorn
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring nginx...                                           **"
echo "**                                                                     **"
echo "*************************************************************************"
# Move into install directory
cd /usr/local/bin/spkr-select-v3/auto-install/nginx

# Delete default configuration
$SUDO rm /etc/nginx/sites-enabled/default

# Copy configuration file to nginx
$SUDO cp spkr-select.nginx /etc/nginx/sites-available/spkr-select

# Create link in sites-enabled
$SUDO ln -s /etc/nginx/sites-available/spkr-select /etc/nginx/sites-enabled

whiptail --msgbox --backtitle "SSL Certs" --title "Speaker-Select Automated Installer" "The script will now open a text editor to edit a configuration file for the cert generation.  Fill in the defaults you'd like the signing to use for your instance and when finished, press CTRL+x to save and exit." ${r} ${c}

cd /usr/local/bin/spkr-select-v3/certs

# Modify the localhost configuration file
$SUDO nano localhost.conf

# Create public and private key pairs based on localhost.conf information
$SUDO openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout localhost.key -out localhost.crt -config localhost.conf

# Move the public key to the /etc/ssl/certs directory
$SUDO mv localhost.crt /etc/ssl/certs/localhost.crt
# Move the private key to the /etc/ssl/private directory
$SUDO mv localhost.key /etc/ssl/private/localhost.key

# Restart nginx
$SUDO service nginx restart

### Setup Supervisor to Start Apps on Boot / Restart on Failures
clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Supervisord...                                     **"
echo "**                                                                     **"
echo "*************************************************************************"

# Copy configuration files (control.conf, webapp.conf) to supervisor config directory
# NOTE: If you used a different directory for the installation then make sure you edit the *.conf files appropriately
cd /usr/local/bin/spkr-select-v3/auto-install/supervisor

$SUDO cp *.conf /etc/supervisor/conf.d/

SVISOR=$(whiptail --title "Would you like to enable the supervisor WebUI?" --radiolist "This allows you to check the status of the supervised processes via a web browser, and also allows those processes to be restarted directly from this interface. (Recommended)" 20 78 2 "ENABLE_SVISOR" "Enable the WebUI" ON "DISABLE_SVISOR" "Disable the WebUI" OFF 3>&1 1>&2 2>&3)

if [[ $SVISOR = "ENABLE_SVISOR" ]];then
   echo " " | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "[inet_http_server]" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   echo "port = 9001" | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   USERNAME=$(whiptail --inputbox "Choose a username [default: user]" 8 78 user --title "Choose Username" 3>&1 1>&2 2>&3)
   echo "username = " $USERNAME | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   PASSWORD=$(whiptail --passwordbox "Enter your password" 8 78 --title "Choose Password" 3>&1 1>&2 2>&3)
   echo "password = " $PASSWORD | sudo tee -a /etc/supervisor/supervisord.conf > /dev/null
   whiptail --msgbox --backtitle "Supervisor WebUI Setup" --title "Setup Completed" "You now should be able to access the Supervisor WebUI at http://your.ip.address.here:9001 with the username and password you have chosen." ${r} ${c}
else
   echo "No WebUI Setup."
fi

echo "Starting Supervisor Service..."
# If supervisor isn't already running, startup Supervisor
$SUDO service supervisor start

# Check if the user would like to install IR support.  
if (whiptail --title "Setup IR Support" --yesno "Do you want to setup IR support?" 8 78); then
	if grep -Fxq "dtoverlay=gpio-ir,gpio_pin=27" /boot/config.txt 
	then
    	echo "/boot/config.txt already setup with GPIO pin 27, skipping step."
	else
    	echo "Adding GPIO Pin 27, IR Support to the /boot/config.txt file..."
    	echo "dtoverlay=gpio-ir,gpio_pin=27" | $SUDO tee -a /boot/config.txt > /dev/null
	fi
	# Let the user know that the installation needs to be completed after a reboot
	whiptail --msgbox --backtitle "Install Almost Complete / Reboot Required" --title "Reboot" "Congratulations, the installation is almost complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  To continue to setup the IR Remote capability after the reboot, ssh into the pi again and run 'bash ~/spkr-select-v3/auto-install/setup_ir.sh'.  This should walk through the steps to complete your setup." ${r} ${c}
else
    echo "Skipping IR Setup."
	whiptail --msgbox --backtitle "Install Complete / Reboot Required" --title "Installation Completed - Rebooting" "Congratulations, the installation is complete.  At this time, we will perform a reboot and your application should be ready.  You should be able to access your application by opening a browser on your PC or other device and using the IP address for this Pi.  Enjoy!" ${r} ${c}
fi

# Rebooting
$SUDO reboot
