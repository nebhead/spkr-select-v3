---
title: "Home Assistant Setup"
permalink: /ha
sort: 7
---

## Home Assistant Setup 

It should be noted that I am a beginner, at best, when it comes to configuring Home Assistant.  I have setup a basic configuration that can be added to the config.yaml file (or wherever you have your configuration for HA).  This configuration adds a set of switches that utilize the local API on the speaker select box.  You'll need to modify your IP address and names, etc.  

Example YAML from my setup: 

```yaml
switch speakers:
- platform: rest
  name: "Living Room Speakers"
  resource: http://192.168.10.42/api
  scan_interval: 30
  body_on: '{"spkr_00": "on"}'
  body_off: '{"spkr_00": "off"}'
  is_on_template: "{{ value_json.spkr_00 == 'on' }}"
  headers:
    Content-Type: application/json
  verify_ssl: false
- platform: rest
  name: "Kitchen Speakers"
  resource: http://192.168.10.42/api
  scan_interval: 31
  body_on: '{"spkr_01": "on"}'
  body_off: '{"spkr_01": "off"}'
  is_on_template: "{{ value_json.spkr_01 == 'on' }}"
  headers:
    Content-Type: application/json
  verify_ssl: false
- platform: rest
  name: "Dining Room Speakers"
  resource: http://192.168.10.42/api
  scan_interval: 32
  body_on: '{"spkr_02": "on"}'
  body_off: '{"spkr_02": "off"}'
  is_on_template: "{{ value_json.spkr_02 == 'on' }}"
  headers:
    Content-Type: application/json
  verify_ssl: false
```

Once configured, you can add these entities to your dashboard configuration.  It also means that you can use Google Assistant or Amazon Echo (if setup in HA) to control the state of these switches.  And that's something, right?  