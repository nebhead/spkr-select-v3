"""
 *****************************************
  Speaker Selector Control Python script
 *****************************************

	Description: This script will read the states from Redis and set relays/LEDs
	upon any changes to the database.  This script also accepts input from the IR
	sensor and will update Redis and set the relays appropriately.

	This script runs as a separate process from the Flask / Gunicorn
	implementation which handles the web interface.

 *****************************************
"""

import time
import redis
from common import *

def main():
	"""
	 *****************************************
	   Main Program Start / Init
	 *****************************************
	"""
	event = 'Control Script Starting.'
	WriteLog(event, logger_name='control')

	status = redis.Redis()
	status.flushall()
	status.set('update_settings', 0)

	settings = ReadJSON('settings')

	if is_raspberrypi():
		from platform_raspi import RasPiPlatform as SpeakerPlatform
	else:
		from platform_base import SpeakerPlatform

	platform = SpeakerPlatform(settings)

	"""
	 *****************************************
	   Main Program Loop
	 *****************************************
	"""

	while True:
		# 1. Check if input from Web UI / REST API and set outputs
		platform.check_appinput()

		# 2. Check if input from buttons and set outputs
		platform.check_buttons()

		# 3. Check if input from IR Remote Control and set outputs
		platform.check_ir_input()

		# 4. Check if change in settings needed 
		if(status.get('update_settings') == 1):
			settings = ReadJSON('settings')
			platform.update_settings(settings)
			status.set('update_settings', 0)

		time.sleep(0.01)

if __name__ == "__main__":
    main()
