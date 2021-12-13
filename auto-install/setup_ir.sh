#!/usr/bin/env bash

# Speaker-Select IR Setup Script
# Many thanks to the PiVPN project (pivpn.io) for much of the inspiration for this script

# WARNING: Do NOT run with SUDO or the cd commands will not work properly (i.e. they will use root
# instead of the pi user).  This command will automatically get SUDO and use in the proper places.

# Obtain ROOT for needed operations
if [[ $EUID -eq 0 ]];then
    echo "You are running this script as root."
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

# Check if the GPIO pin definition has been added to the boot/config.txt
if grep -Fxq "dtoverlay=gpio-ir,gpio_pin=27" /boot/config.txt 
then
	echo "GPIO config detected in config.txt, all good!"
else
	# Check if the user would like to install IR support.  
	if (whiptail --title "Add GPIO to config.txt" --yesno "It appears the GPIO definition isn't added to the config.txt.  Add it and reboot? (selecting NO will exit)" 8 78); then
		echo "Adding GPIO Pin 27, IR Support to the /boot/config.txt file..."
		echo "dtoverlay=gpio-ir,gpio_pin=27" | $SUDO tee -a /boot/config.txt > /dev/null
		echo "*************************************************************************"
		echo "**                                                                     **"
		echo "**      After reboot, run this script again to complete setup.         **"
		echo "**                                                                     **"
		echo "*************************************************************************"
		echo ""
		echo "Rebooting..."
		$SUDO reboot 
		return
	else
		echo "Exiting... "
		return
	fi
fi

clear
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Enable different remote types                                  **"
echo "**                                                                     **"
echo "*************************************************************************"
# Enable remote types
$SUDO ir-keytable -p rc-5,rc-5-sz,jvc,sony,nec,sanyo,mce_kbd,rc-6,sharp,xmp

# Check if user would like to custom configure their remote control and IR codes
if (whiptail --title "Custom IR Remote Setup" --yesno "Do you want to use custom remote scan codes? (if NO selected, then use default setup)" 8 78); then
	# Check if user wants to manually configure key input or use the default key input
	whiptail --msgbox --backtitle "IR Setup" --title "Get Scan Codes" "The script will now open the ir-keytable test application.  Use this application to capture the IR remote keys you would like to use.  After you press enter, aim your remote at the reciever, press the keys on your remote that you want to use, and write down the scan codes.  Press CTRL+C exit." ${r} ${c}
	
	# Run the ir-keytable test 
	$SUDO ir-keytable -t &
	# This is needed to ignore CTRL-C
	pidtest = $!
	trap "kill -1 $pidtest" SIGINT
	wait $pidtest 

	whiptail --msgbox --backtitle "IR Setup" --title "Edit Config TOML" "The script will now open the TOML file in a text editor, edit the scancodes that you captured in the previous step for the different buttons.  Press CTRL+X to save and exit." ${r} ${c}
	cd /home/pi/spkr-select-v3/
	nano spkrselect.toml
fi

# Clear the current configuration
$SUDO ir-keytable -c

# Write your new configuration

$SUDO ir-keytable -w /home/pi/spkr-select-v3/spkrselect.toml

# Read the configuration

$SUDO ir-keytable -r

#Test the configuration
whiptail --msgbox --backtitle "IR Setup" --title "Test Your Configuration" "The script will now open the ir-keytable test application.  Use this application to test that your IR Scan Codes are working.  You should see the remote keys mapped to KEY_A, KEY_D, KEY_0, ... etc. as you press them.  Press CTRL+C exit." ${r} ${c}

$SUDO ir-keytable -t

# Check if user would like to custom configure their remote control and IR codes
if (whiptail --title "Confirm Setup" --yesno "Did your settings work properly?" 8 78); then
	whiptail --msgbox --backtitle "IR Setup" --title "Test Your Configuration" "Great!  Let's finalize the settings and finish up." ${r} ${c}
else 
	whiptail --msgbox --backtitle "IR Setup" --title "Test Your Configuration" "Sorry to hear that didn't work.  Please re-run this script and try again." ${r} ${c}
	return
fi

# First we need to copy the spkrselect.toml file to the correct location:
cd /home/pi/spkr-select-v3/
$SUDO cp spkrselect.toml /etc/rc_keymaps/

# Now, add a row in /etc/rc_maps.cfg:
whiptail --msgbox --backtitle "IR Setup" --title "Edit /etc/rc_maps.cfg" "The script will now open the /etc/rc_maps.cfg file in a text editor. Add this line to the *beginning* of the list of configuration files: * * spkrselect.toml   Then press ctrl-o to write the file, and ctrl-x to exit." ${r} ${c}
$SUDO nano /etc/rc_maps.cfg

### Edit CRONTAB to persist IR settings on reboot
echo "*************************************************************************"
echo "**                                                                     **"
echo "**      Configuring Crontab to setup ir-ketyable on reboot...          **"
echo "**                                                                     **"
echo "*************************************************************************"

cd /home/pi/spkr-select-v3/
$SUDO crontab -l > my-crontab
# Add the following line...
echo "@reboot ir-keytable -a /etc/rc_maps.cfg -s rc0" >> my-crontab
$SUDO crontab my-crontab
rm my-crontab

# Setup Complete! 
whiptail --msgbox --backtitle "IR Setup" --title "IR Setup Complete" "Congratulations!  The IR remote setup is now complete.  You may now enable IR via settings in the WebUI.  Reboot is required." ${r} ${c}
clear
echo "All Done!  Have a wonderful day!"
echo "Rebooting..."
$SUDO reboot