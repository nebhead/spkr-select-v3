"""
 *****************************************
 	Speaker Select Platform Class (BASE)
 *****************************************

 Description: This library supports 
  controlling the outputs and observing
  inputs on the hardware platform

 *****************************************
"""

"""
 *****************************************
 	Imported Libraries
 *****************************************
"""

import redis
import json

"""
 *****************************************
 	Parent Class Definition 
 *****************************************
"""

class SpeakerPlatform: 
	def __init__(self, settings):
		self.cmdsts = redis.Redis()
		self.settings = settings
		self.spkr_state = {}

		self._init_relays()

		self._init_ir()

		self._init_buttons()

	def _init_relays(self):
		"""
		 Setup relays (and LEDS) in default state, or reconfigure
		"""

		if(self.spkr_state == {}):
			self.spkr_state = {
				'spkr_00' : 'off',
				'spkr_01' : 'off', 
				'spkr_02' : 'off',
				'spkr_03' : 'off',
				'spkr_pro' : 'off'
			}

			for key, value in self.spkr_state.items():
				if key != 'spkr_pro':
					if(self.settings['spkr_config'][key]['default'] == 'nc'):
						self.spkr_state[key] = 'on'  # For normally connected
					else: 
						self.spkr_state[key] = 'off'  # For normally open

		self.set_relays()

	def _init_ir(self):
		pass 

	def _init_buttons(self):
		self.buttons = {}
		for key, value in self.spkr_state.items():
			if(key != 'spkr_pro'):
				self.buttons[key] = False
		
		self.cmdsts.set('buttons', json.dumps(self.buttons))

	def _read_states(self):
		return(json.loads(self.cmdsts.get('speakers')))

	def _write_states(self):
		self.cmdsts.set('speakers', json.dumps(self.spkr_state))

	def update_settings(self, settings):
		self.settings = settings 
		self._init_relays()
		self._init_ir()
		self._init_buttons() 

	def set_relays(self):
		"""
		 *****************************************
		  Simple function to set relay and LED outputs
		 *****************************************
		"""
		# In base, only check protection (set protection as needed)
		self.check_protection()
		# Commit changes to database
		self._write_states()

	def check_appinput(self):
		current_state = self._read_states()
		if(current_state != self.spkr_state):
			self.spkr_state = current_state.copy()
			self.set_relays()

	def check_buttons(self):
		"""
		 *****************************************
		  Check for input from front panel buttons
		 *****************************************
		"""
		self.buttons = json.loads(self.cmdsts.get('buttons'))
		for key, value in self.spkr_state.items(): 
			if (key != 'spkr_pro'): 
				if (self.buttons[key]): 
					self.button_pressed(key)
					self.buttons[key] = False
					self.cmdsts.set('buttons', json.dumps(self.buttons))

	def button_pressed(self, spkr_key):
		if(self.spkr_state[spkr_key] == 'on'):
			self.spkr_state[spkr_key] = 'off'
		else:
			self.spkr_state[spkr_key] = 'on'
		self.set_relays()

	def check_ir_input(self):
		"""
		*****************************************
		Check for input from IR remote control
		*****************************************
		"""
		pass 

	def check_protection(self):
		"""
		 *****************************************
		  Function: SetProtection
		  Input: spkr_state dict
		  Description: Set Protection On/Off as needed
		 *****************************************
		"""
		spkr_ohms = 0
		for key, value in self.spkr_state.items():
			if(key != 'spkr_pro'): 
				if(value == 'on'):
					spkr_ohms += (1 / self.settings['spkr_config'][key]['impedance'])

		# Calculate Impedance R = 1 / (1/R1) + (1/R2) ... + (1/RN)
		if spkr_ohms > 0: 
			spkr_ohms = (1 / spkr_ohms)
			if (spkr_ohms < 4):
				self.spkr_state['spkr_pro'] = 'on'
			else:
				self.spkr_state['spkr_pro'] = 'off'
		else:
			self.spkr_state['spkr_pro'] = 'off'
		
		
