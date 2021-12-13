"""
 *****************************************
 	Speaker Select Platform Class (RasPi)
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

import gpiozero
import evdev
import time
from common import WriteLog
from platform_base import SpeakerPlatform

"""
 *****************************************
 	Inherited Class Definition 
 *****************************************
"""

class RasPiPlatform(SpeakerPlatform): 
	def __init__(self, settings):
		super().__init__(settings)

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

		if self.settings['options']['triggerlevel'] == 'LOW': # Defines for Active LOW relay
			self.RELAY_ACTIVE_HIGH = False
		else: # Defines for Active HIGH relay (true = HIGH)
			self.RELAY_ACTIVE_HIGH = True

		self.led_list = {}
		self.relay_list = {}

		# Setup Relays & LEDs for Speakers Selections
		for key, value in self.spkr_state.items():
			if(key != 'spkr_pro'):
				self.led_list[key] = gpiozero.LED(self.settings['spkr_config'][key]['gpio_led_pin'])
				self.relay_list[key] = gpiozero.OutputDevice(self.settings['spkr_config'][key]['gpio_relay_pin'], active_high=self.RELAY_ACTIVE_HIGH)
		
		# Setup Relay & LED for Speaker Protection
		self.led_list['spkr_pro'] = gpiozero.LED(self.settings['protection']['gpio_led_pin'])
		self.relay_list['spkr_pro'] = gpiozero.OutputDevice(self.settings['protection']['gpio_relay_pin'], active_high=self.RELAY_ACTIVE_HIGH)

		self.check_protection()
		self._write_states()
		self.set_relays()

	def _init_ir(self):
		self.debounceir = 0
		if(self.settings['options']['ir_input'] == True):
			devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
			self.remotecontrol = None
			for device in devices:
				if device.name == "gpio_ir_recv":
					self.remotecontrol = device
					break
	
			if not self.remotecontrol:
				event = 'Error setting up IR Input: gpio_ir_recv not found in list of devices.'
				WriteLog(event)
				# Disable ir_input
				self.settings['options']['ir_input'] = False

	def _init_buttons(self):
		self.buttons_list = {}
		for key, value in self.spkr_state.items(): 
			if (key != 'spkr_pro'):
				self.buttons_list[key] = gpiozero.Button(self.settings['spkr_config'][key]['gpio_btn_pin'],  pull_up=False, bounce_time=0.1)
				self.buttons_list[key].when_pressed = self.button_pressed

	def button_pressed(self, button):
		for key, value in self.spkr_state.items():
			if(key != 'spkr_pro'):
				pin = 'GPIO' + str(self.settings['spkr_config'][key]['gpio_btn_pin'])
				if(pin == str(button.pin)) and (self.settings['spkr_config'][key]['enabled']):
					print(f'Match Found! {key}')
					if(self.spkr_state[key] == 'on'):
						self.spkr_state[key] = 'off'
					else:
						self.spkr_state[key] = 'on'
					self.set_relays()

	def set_relays(self):
		"""
		 *****************************************
		  Simple function to set relay and LED outputs
		 *****************************************
		"""
		# First enable speaker protection, before enabling other speakers
		self.check_protection()
		if self.spkr_state['spkr_pro'] == 'on':
			self.relay_list['spkr_pro'].on()
			self.led_list['spkr_pro'].on()
		else: 
			self.relay_list['spkr_pro'].off()
			self.led_list['spkr_pro'].off()

		for key, value in self.spkr_state.items():
			if key != 'spkr_pro':
				if((self.settings['spkr_config'][key]['default'] == 'nc') and (value=='on'))or((self.settings['spkr_config'][key]['default'] == 'no') and (value=='off')):
					self.relay_list[key].off() 	# For normally connected
				else: 
					self.relay_list[key].on() 	# For normally open
				
				if(value == 'on'): 
					self.led_list[key].on() 	# Turn on LED
				else: 
					self.led_list[key].off() 	# Turn off LED
		# Commit changes to Database
		self._write_states()

	def check_buttons(self):
		"""
		 *****************************************
		  Check for input from front panel buttons
		 *****************************************
		"""
		pass	

	def check_ir_input(self):
		"""
		*****************************************
		Check for input from IR remote control
		*****************************************
		"""
		if(self.settings['options']['ir_input'] == True):
			pressed = self.remotecontrol.active_keys(verbose=True)
			if(pressed != []) and (self.debounceir <= time.time()):
				self.debounceir = time.time() + 0.6
				if('KEY_A' in pressed[0]): 
					print('KEY_A pressed, turning on all enabled speakers.')
					for key, value in self.settings['spkr_config'].items():
						if(key != 'spkr_pro'):
							if(self.settings['spkr_config'][key]['enabled'] == True):
								self.spkr_state[key] = 'on'
					self.set_relays()
				elif('KEY_D' in pressed[0]):
					print('KEY_D pressed, turning on default enabled speakers.')
					for key, value in self.settings['spkr_config'].items():
						if(key != 'spkr_pro'):
							if(self.settings['spkr_config'][key]['default'] == 'nc') and (self.settings['spkr_config'][key]['enabled'] == True):
								self.spkr_state[key] = 'on'
							else: 
								self.spkr_state[key] = 'off'
					self.set_relays()
				else:
					for key, value in self.settings['spkr_config'].items(): 
						if (key != 'spkr_pro'): 
							if (self.settings['spkr_config'][key]['ir_key'] in pressed[0]): 
								if(self.spkr_state[key] == 'on'):
									self.spkr_state[key] = 'off'
								else:
									self.spkr_state[key] = 'on'
					self.set_relays()
