---
title: "Installation"
permalink: /install
sort: 3
---

## Software Installation

### Raspberry Pi Zero Setup Headless (*from raspberrypi.org*)

Once you've burned/etched the Raspbian Stretch Lite image onto the microSD card, connect the card to your working PC and you'll see the card being mounted as "boot". Inside this "boot" directory, you need to make 2 new files. You can create the files using Atom code editor.

+ Step 1: Create an empty file. You can use Notepad on Windows or TextEdit to do so by creating a new file. Just name the file `ssh`. Save that empty file and dump it into boot partition (microSD).

+ Step 2: Create another file name wpa_supplicant.conf . This time you need to write a few lines of text for this file. For this file, you need to use the FULL VERSION of `wpa_supplicant.conf`. Meaning you must have the 3 lines of data namely country, ctrl_interface and update_config

```
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="your_real_wifi_ssid"
    scan_ssid=1
    psk="your_real_password"
    key_mgmt=WPA-PSK
}
```

#### Run RasPi-Config
```bash
$ ssh pi@192.168.1.xxx

$ sudo raspi-config
```
In these menus you should setup up the following: 
+ Set locales
+ Set timezone
+ Replace Hostname with a unique hostname ('i.e. spkr-select')

Finish and reboot.  

### Automatic Software Installation

After you've done the above steps to configure your Raspberry Pi initially, you will need to log in via SSH and at the command line type the following:

```bash
curl https://raw.githubusercontent.com/nebhead/spkr-select-v3/main/auto-install/install.sh | bash
```

Follow the onscreen prompts to complete the installation.  You will be asked to setup cert for the webserver, which is entirely optional.  If you don't plan on using the external API, you can simply enter all blanks in the CERT questions.  At the end of the script it will reboot, so just be aware of this.  

Also note that if you are installing / using the IR Remote capabilities you may need to run the setup_ir.sh script after the reboot.  Simply log back via SSH after your reboot and run the script in the auto-install directory:

```bash
$ bash ~/spkr-select-v3/auto-install/setup_ir.sh
```
