import datetime
import io
import os
import json
import logging 
import ratelimitingfilter

def DefaultSettings():
	settings = {}

	settings['spkr_config'] = {
        'spkr_00' : {
            'name' : 'Living Room', 
            'enabled' : True,
            'default' : 'nc',
            'impedance' : 4, 
            'gpio_relay_pin' : 22,
            'gpio_led_pin' : 17,
            'gpio_btn_pin' : 13,
            'ir_key' : 'KEY_0'  
        },
        'spkr_01' : {
            'name' : 'Kitchen', 
            'enabled' : True,
            'default' : 'no',
            'impedance' : 8, 
            'gpio_relay_pin' : 23,
            'gpio_led_pin' : 18,
            'gpio_btn_pin' : 14,
            'ir_key' : 'KEY_1' 
        },
        'spkr_02' : {
            'name' : 'Dining Room', 
            'enabled' : True,
            'default' : 'no',
            'impedance' : 8, 
            'gpio_relay_pin' : 24,
            'gpio_led_pin' : 19,
            'gpio_btn_pin' : 15,
            'ir_key' : 'KEY_2' 
        },
        'spkr_03' : {
            'name' : 'Unused', 
            'enabled' : False,
            'default' : 'no',
            'impedance' : 8, 
            'gpio_relay_pin' : 25,
            'gpio_led_pin' : 20,
            'gpio_btn_pin' : 16,
            'ir_key' : 'KEY_3' 
        }
    }
	
	settings['protection'] = {
            'name' : 'Speaker Protection', 
            'enabled' : True,
            'default' : 'no',  # This is actually the opposite, but needs to be set this way to work properly
            'impedance' : 2.5, 
            'gpio_relay_pin' : 26,
            'gpio_led_pin' : 21,
            'gpio_btn_pin' : 0,
            'ir_key' : 'KEY_P' 
	}

	settings['ui_config'] = {
        'pagetheme' : 'default', 
        'themes' : {
            'default' : 'Default Light Theme', 
            'dark' : 'Dark Theme'
        }, 
        'auto_theme' : {
            'enabled' : False,  # True - Auto Theme Enabled, False - Static Theme Enabled
            'mode' : 'sunrise_set',  # timeofday, sunrise_set
            'theme_night' : 'dark',
            'theme_day' : 'default', 
            'sunset' : '',
            'sunrise' : '', 
            'location' : '',
			'latitude' : 0,
			'longitude' : 0,  
			'lastupdate' : ''
        },
        'auto_LEDs' : {
            'enabled' : False,
            'mode' : 'timeofday',  # timeofday, sunrise_set
            'time_on' : '',
            'time_off' : '',
			'location' : '', # timezone 
			'lastupdate' : ''
        },
    }

	settings['extapi_config'] = {
        'enabled' : False,  # Disable external API support by default
        'api_key' : ''
    }

	settings['api_config'] = {
        'enabled' : True    # Enable local API support by default 
    }

	settings['options'] = {
        'ir_input' : False,
		'triggerlevel' : 'high',  # Relays are active 'high' enable or active 'low' enable
    }

	return(settings)

def DefaultStates():
    states = {}

    states = {
        'spkr_00' : 'on',
        'spkr_01' : 'off', 
        'spkr_02' : 'off',
        'spkr_03' : 'off',
		'spkr_pro' : 'off'
	}

    return(states)

def ReadJSON(target):
	# *****************************************
	# Read from JSON file
	# *****************************************

	# Get structure format
    if (target == 'settings'):
        outputstruct = DefaultSettings()
        inputfile = 'settings.json'
    else:
        print('No Target')
        return(False)
    try:
        json_data_file = os.fdopen(os.open(inputfile, os.O_RDONLY))
        json_data_string = json_data_file.read()
        json_struct = json.loads(json_data_string)
        json_data_file.close()
    except(IOError, OSError):
        # Issue with reading states JSON, so create one/write new one
        WriteJSON(outputstruct, target)
        return(outputstruct)
    except:
        # Issue with reading states JSON, so create one/write new one
        WriteJSON(outputstruct, target)
        return(outputstruct)

    # Overlay the read values over the top of the default settings
    #  This ensures that any NEW fields are captured.  
    for key in outputstruct.keys():
        outputstruct[key].update(json_struct.get(key, {}))

    return(outputstruct)

def WriteJSON(inputstruct, target):
    # *****************************************
    # Write all settings to JSON file
    # *****************************************
    json_data_string = json.dumps(inputstruct, indent=2, sort_keys=True)

    # Get structure format
    if (target == 'settings'):
        outputstruct = DefaultSettings()
        outputfile = 'settings.json'
    else:
        print('No Target')
        return(False)

    for key in outputstruct.keys():
        outputstruct[key].update(inputstruct.get(key, {}))

    with open(outputfile, 'w') as json_file:
        json_file.write(json_data_string)

def ReadLog():
	# *****************************************
	# Function: ReadLog
	# Input: none
	# Output:
	# Description: Read event.log and populate
	#  an array of events.
	# *****************************************

	# Read all lines of events.log into an list(array)
	try:
		with open('/logs/events.log') as event_file:
			event_lines = event_file.readlines()
			event_file.close()
	# If file not found error, then create events.log file
	except(IOError, OSError):
		event_file = open('/logs/events.log', "w")
		event_file.close()
		event_lines = []

	# Initialize event_list list
	event_list = []

	# Get number of events
	num_events = len(event_lines)

	for x in range(num_events):
		event_list.append(event_lines[x].split(" ",2))

	# Error handling if number of events is less than 10, fill array with empty
	if (num_events < 10):
		for line in range((10-num_events)):
			event_list.append(["--------","--:--:--","---"])
		num_events = 10

	return(event_list, num_events)

def create_logger(name, filename='./logs/global.log', messageformat='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO):
	'''Create or Get Existing Logger'''
	logger = logging.getLogger(name)
	''' 
		If the logger does not exist, create one. Else return the logger. 
		Note: If the a log-level change is needed, the developer should directly set the log level on the logger, instead of using 
		this function.  
	'''
	if not logger.hasHandlers():
		logger.setLevel(level)
		formatter = logging.Formatter(fmt=messageformat, datefmt='%Y-%m-%d %H:%M:%S')
		# datefmt='%Y-%m-%d %H:%M:%S'
		# Add a rate limit filter to reduce multiple rapid bursts of errors 
		#config = {'match': ['Put String Filter Here']}
		#ratelimit = RateLimitingFilter(rate=1, per=60, burst=5, **config)  # Allow 1 per 60s (with periodic burst of 5)
		handler = logging.FileHandler(filename)        
		handler.setFormatter(formatter)
		#handler.addFilter(ratelimit)  # Add the rate limit filter
		logger.addHandler(handler)
	return logger

def WriteLog(event, logger_name='global'):
	# *****************************************
	# Function: WriteLog
	# Input: str event
	# Description: Write event to event.log
	#  Event should be a string.
	# *****************************************
    """
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	logfile = open("logs/events.log", "a")
	logfile.write(now + ' ' + event + '\n')
	logfile.close()
	"""
    logger = create_logger(logger_name)
    logger.info(event)
      
'''
is_raspberrypi() function borrowed from user https://raspberrypi.stackexchange.com/users/126953/chris
  in post: https://raspberrypi.stackexchange.com/questions/5100/detect-that-a-python-program-is-running-on-the-pi
'''
def is_raspberrypi():
	try:
		with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
			if 'raspberry pi' in m.read().lower(): return True
	except Exception: pass
	return False
