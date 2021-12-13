"""
 *****************************************
  Speaker Selector Flask/Python Script
 *****************************************

	Description: This script provides the WebUI and API for 
	the Speaker Selector.  This application can watch the Redis DB
	for changes, and can make changes for Redis DB.  

 *****************************************
"""


from flask import Flask, request, render_template, make_response, jsonify, abort, redirect
import os
import secrets
from common import *  # Common Library for WebUI and Control Program
import redis # pip3 install redis
from geocheck import *  # Library for checking location / sunrise / sunset

settings = ReadJSON('settings')

app = Flask(__name__)

cmdsts = redis.Redis()

@app.route('/')
def index():
	global settings
	button_list = build_button_list()
	
	return render_template('dash.html', button_list=button_list, settings=settings, pagetheme=get_theme())

@app.route('/dash')
def dash():
	return redirect('/')

@app.route('/fp')
def frontpanel():
	'''
	This is for testing purposes only.  
	Testing prototype physical buttons.  
	'''
	global settings
	button_list = build_button_list()

	if(is_raspberrypi()):
		warning = 'WARNING: This page will not work on a Raspberry Pi.'
	else:
		warning = 'none'

	return render_template('front_panel.html', button_list=button_list, settings=settings, pagetheme=get_theme(), warning=warning)

@app.route('/geocheck', methods=['POST'])
def geocheck():

	if (request.method == 'POST'):
		response = request.form

		if(response['location'] != ''):
			#print(f'Location Request: {response["location"]}')
			result = location_check(response['location'])
			
			if(result['success']):
				result = get_sunrise_sunset(result['latitude'], result['longitude'])
				#print(f'Result Data Structure: {result}')
				return jsonify(result)

	return jsonify({ 'success' : False })


@app.route('/states')
def states():
	button_list = build_button_list()
	return jsonify(button_list)

@app.route('/button', methods=['POST'])
def button():
	global settings

	if (request.method == 'POST'):
		global cmdsts
		response = request.form
		spkr_state = read_states()
		
		if('all_on' in response):
			for key, value in settings['spkr_config'].items():
				if(settings['spkr_config'][key]['enabled'] == True):
					spkr_state[key] = 'on'
			write_states(spkr_state)
		
		elif('defaults' in response):
			for key, value in settings['spkr_config'].items():
				if(settings['spkr_config'][key]['default'] == 'nc') and (settings['spkr_config'][key]['enabled'] == True):
					spkr_state[key] = 'on'
				else: 
					spkr_state[key] = 'off'
			write_states(spkr_state)

		elif('keyname' in response):
			keyname = response['keyname']
			if(spkr_state[keyname] == 'off'):
				spkr_state[keyname] = 'on'
			else:
				spkr_state[keyname] = 'off'
			write_states(spkr_state)

		# For testing purposes
		elif('fp_button' in response):
			keyname = response['fp_button']
			buttons = {}
			for key, value in spkr_state.items():
				if (key != 'spkr_pro'):
					if(keyname == key):
						buttons[key] = True
					else:
						buttons[key] = False 
			cmdsts.set('buttons', json.dumps(buttons))
			

		return jsonify({ 'result' : 'success' })
	else:
		return jsonify({ 'result' : 'failed' })

@app.route('/activebuttons', methods=['POST','GET'])
def activebuttons():
	global settings 
	spkr_state = read_states()
	return render_template('activeb.html', spkr_state=spkr_state, settings=settings)

@app.route('/irinfo')
def irinfo():
	global settings
	return render_template('irinfo.html', settings=settings, pagetheme=get_theme())

@app.route('/admin/<action>', methods=['POST','GET'])
@app.route('/admin', methods=['POST','GET'])
def admin(action=None):
	global settings 

	notify = {}
	notify['type'] = ''
	notify['message'] = ''

	if (request.method == 'POST') and (action == 'api_settings'):
		response = request.form
		if('apienable' in response):
			if(response['apienable']=='on'):
				settings['api_config']['enabled'] = True
				WriteJSON(settings, 'settings')
		else:
			settings['api_config']['enabled'] = False
			WriteJSON(settings, 'settings')

		notify['type'] = 'success'
		notify['message'] = 'Local API Settings Updated Succesfully.'

	if (request.method == 'POST') and (action == 'extapi_settings'):
		response = request.form
		#print(response)
		if('apienable' in response):
			if(response['apienable']=='on'):
				settings['extapi_config']['enabled'] = True
				WriteJSON(settings, 'settings')
				notify['type'] = 'success'
				notify['message'] = 'External API Enabled Succesfully.'
		else:
			settings['extapi_config']['enabled'] = False
			WriteJSON(settings, 'settings')
			notify['type'] = 'success'
			notify['message'] = 'External API Disabled Succesfully.'

		if('apigen' in response):
			if(response['apigen']=='requested'):
				settings['extapi_config']['api_key'] = gen_api_key(32)
				WriteJSON(settings, 'settings')
				notify['type'] = 'success'
				notify['message'] = 'External API Key Updated.'

	if (request.method == 'POST') and (action == 'settings'):
		response = request.form
		#print(response)

		if('ir_input' in response):
			if(response['ir_input'] == 'true'): 
				settings['options']['ir_input'] = True
				notify['message'] = 'Succesfully enabled IR input.'
			else: 
				settings['options']['ir_input'] = False 
				notify['message'] = 'Succesfully disabled IR input.'
			WriteJSON(settings, 'settings')
			update_settings()
			notify['type'] = 'success'
			

		if('auto_theme_update' in response):
			if (response['at_location'] != ''):
				location = response['at_location']
				result = location_check(location)
			
				if(result['success']):
					result = get_sunrise_sunset(result['latitude'], result['longitude'])
					#print(f'Result Data Structure: {result}')
					settings['ui_config']['auto_theme']['enabled'] = True 
					settings['ui_config']['auto_theme']['mode'] = 'sunrise_set'
					settings['ui_config']['auto_theme']['latitude'] = result['latitude'] 
					settings['ui_config']['auto_theme']['longitude'] = result['longitude'] 
					settings['ui_config']['auto_theme']['sunrise'] = result['sunrise']
					settings['ui_config']['auto_theme']['sunset'] = result['sunset']
					settings['ui_config']['auto_theme']['location'] = location
					settings['ui_config']['auto_theme']['lastupdate'] = result['lastupdate']
					WriteJSON(settings, 'settings')
					notify['type'] = 'success'
					notify['message'] = f'Succesfully enabled Auto-Theme for {location}.'
				else: 
					#print(f'Failed with location: {location}')
					notify['type'] = 'error'
					notify['message'] = f'Failed to enable auto theme with location set to {location}!'
			else: 
				notify['type'] = 'error'
				notify['message'] = 'Failed to enable auto theme with no location set!'

		if('static_theme_update' in response):
			settings['ui_config']['auto_theme']['enabled'] = False  # Set the Theme mode to Static
			settings['ui_config']['pagetheme'] = response['staticThemeSelect']
			WriteJSON(settings, 'settings')
			notify['type'] = 'success'
			notify['message'] = f'Succesfully enabled Static Theme.'

		if('triggerlevel' in response):
			if response['triggerlevel'] == 'high':
				settings['options']['triggerlevel'] = 'high'
				WriteJSON(settings, 'settings')
				update_settings()
			else: 
				settings['options']['triggerlevel'] = 'low'
				WriteJSON(settings, 'settings')
				update_settings()
			notify['type'] = 'success'
			notify['message'] = f'Succesfully changed the Trigger Level to {settings["options"]["triggerlevel"]}.'

		if('config_update' in response):
			spkr_state = read_states()
			for key, value in settings['spkr_config'].items():
				if(key != 'spkr_pro'):
					if(key + "_name" in response):
						settings['spkr_config'][key]['name'] = response[key + "_name"]
					if(key + "_enabled" in response):
						if (response[key + '_enabled'] == 'on'):
							settings['spkr_config'][key]['enabled'] = True
					else: 
						settings['spkr_config'][key]['enabled'] = False
						spkr_state[key] = 'off'
					if(key + "_impedance" in response):
						settings['spkr_config'][key]['impedance'] = int(response[key + '_impedance'])
					if(key + "_default" in response):
						if (response[key + '_default'] == 'nc'):
							settings['spkr_config'][key]['default'] = 'nc'
						else: 
							settings['spkr_config'][key]['default'] = 'no'
			WriteJSON(settings, 'settings')
			update_settings()
			notify['type'] = 'success'
			notify['message'] = 'Succesfully updated speaker configuration.'

	if action == 'reboot':
		event = "Admin: Reboot"
		WriteLog(event)
		if(is_raspberrypi()):
			os.system("sleep 3 && sudo reboot &")
		return render_template('shutdown.html', action=action, pagetheme=settings['ui_config']['pagetheme'])

	elif action == 'shutdown':
		event = "Admin: Shutdown"
		WriteLog(event)
		if(is_raspberrypi()):
			os.system("sleep 3 && sudo shutdown -h now &")
		return render_template('shutdown.html', action=action, pagetheme=settings['ui_config']['pagetheme'])

	uptime = os.popen('uptime').readline()

	cpuinfo = os.popen('cat /proc/cpuinfo').readlines()

	if(is_raspberrypi()):
		ifconfig = os.popen('ifconfig').readlines()
		temp = checkcputemp()
	else:
		ifconfig = 'NA'
		temp = 'NA'

	return render_template('admin.html', settings=settings, notify=notify, uptime=uptime, cpuinfo=cpuinfo, temp=temp, ifconfig=ifconfig, pagetheme=get_theme())

@app.route('/manifest')
def manifest():
    res = make_response(render_template('manifest.json'), 200)
    res.headers["Content-Type"] = "text/cache-manifest"
    return res

@app.route('/api', methods=['POST','GET'])
def api(action=None):
	global settings 
	ipaddress = request.remote_addr

	if (settings['api_config']['enabled'] == True):
		if (request.method == 'POST'):
			if not request.json:
				event = "Local API Call Failed - Local API interface not enabled.  Calling IP: " + ipaddress
				WriteLog(event)
				abort(400)
			else:
				spkr_state = read_states()
				if('spkr_00' in request.json):
					spkr_state['spkr_00'] = request.json['spkr_00']
				if('spkr_01' in request.json):
					spkr_state['spkr_01'] = request.json['spkr_01']
				if('spkr_02' in request.json):
					spkr_state['spkr_02'] = request.json['spkr_02']
				if('spkr_03' in request.json):
					spkr_state['spkr_03'] = request.json['spkr_03']

				write_states(spkr_state)
				event = "Local API Call Success from " + ipaddress
				#WriteLog(event)
				return jsonify({'spkr_00' : spkr_state['spkr_00'], 
					'spkr_01' : spkr_state['spkr_01'],
					'spkr_02' : spkr_state['spkr_02'],
					'spkr_03' : spkr_state['spkr_03']}), 201
			
		if (request.method == 'GET'):
			event = "Local API Call Success from " + ipaddress
			#WriteLog(event)
			spkr_state = read_states()
			return jsonify({'spkr_00' : spkr_state['spkr_00'], 
							'spkr_01' : spkr_state['spkr_01'],
							'spkr_02' : spkr_state['spkr_02'],
							'spkr_03' : spkr_state['spkr_03']}), 201

	event = 'Local API Call Failed from ' + ipaddress
	WriteLog(event)

	abort(404)

@app.route('/extapi/<action>', methods=['POST','GET'])
@app.route('/extapi', methods=['POST','GET'])
def extapi(action=None):
	global settings

	ipaddress = request.remote_addr

	if(action):
		event = "External API Call with key: " + str(action) + " from " + str(ipaddress)
		WriteLog(event)
	else:
		event = "External API Call with no key from " + str(ipaddress)
		WriteLog(event)

	if (settings['extapi_config']['enabled'] == True):
		if (request.method == 'POST') and (action == settings['extapi_config']['api_key']):
			if not request.json:
				event = "External API Call from " + str(ipaddress) + " failed due to to absence of JSON data."
				WriteLog(event)
				abort(400)
			else:
				spkr_state = read_states()
				if('spkr_00' in request.json):
					spkr_state['spkr_00'] = request.json['spkr_00']
				if('spkr_01' in request.json):
					spkr_state['spkr_01'] = request.json['spkr_01']
				if('spkr_02' in request.json):
					spkr_state['spkr_02'] = request.json['spkr_02']
				if('spkr_03' in request.json):
					spkr_state['spkr_03'] = request.json['spkr_03']

			write_states(spkr_state)
			event = "External API Call Success from " + ipaddress
			WriteLog(event)
			return jsonify({'spkr_00' : spkr_state['spkr_00'], 
				'spkr_01' : spkr_state['spkr_01'],
				'spkr_02' : spkr_state['spkr_02'],
				'spkr_03' : spkr_state['spkr_03']}), 201
			
		if (request.method == 'GET') and (action == settings['extapi_config']['api_key']):
			spkr_state = read_states()
			event = "External API Call Success from " + ipaddress
			WriteLog(event)
			return jsonify({'spkr_00' : spkr_state['spkr_00'], 
							'spkr_01' : spkr_state['spkr_01'],
							'spkr_02' : spkr_state['spkr_02'],
							'spkr_03' : spkr_state['spkr_03']}), 201

	ipaddress = request.remote_addr
	event = 'External API Call Failed from ' + ipaddress
	WriteLog(event)

	abort(404)

	# Attribution to Vladimir Ignatyev on Stack Overflow
	# https://stackoverflow.com/questions/41969093/how-to-generate-passwords-in-python-2-and-python-3-securely
def gen_api_key(length, charset="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"):
    return "".join([secrets.choice(charset) for _ in range(0, length)])

def checkcputemp():
	if is_raspberrypi():
		temp = os.popen('vcgencmd measure_temp').readline()
		return temp.replace("temp=","")
	else:
		return("NA")

def read_states():
	global cmdsts
	try: 
		spkr_state = json.loads(cmdsts.get('speakers'))
		return(spkr_state)
	except:
		event = "Error reading speakers state from Redis.  Please ensure control.py is running."
		WriteLog(event)
		spkr_state = DefaultStates()
		return(spkr_state)

def write_states(spkr_state):
	global cmdsts
	cmdsts.set('speakers', json.dumps(spkr_state))

def update_settings():
	global cmdsts
	cmdsts.set('update_settings', 1)

def build_button_list():
	global settings
	spkr_state = read_states()

	button_list = []

	for key, value in spkr_state.items():
		if(key == 'spkr_pro'):
			button = {}
			button['name'] = settings['protection']['name']
			button['keyname'] = key
			button['state'] = value 
			button_list.append(button)
		elif(settings['spkr_config'][key]['enabled']):
			button = {}
			button['name'] = settings['spkr_config'][key]['name']
			button['keyname'] = key
			button['state'] = value 
			button_list.append(button)
	
	return(button_list)

def get_theme():
	global settings
	if(settings['ui_config']['auto_theme']['enabled']):
		if(not is_current(settings['ui_config']['auto_theme']['lastupdate'])):
			# If sunrise/sunset is older than specific amount of days, refresh the information and save
			result = get_sunrise_sunset(settings['ui_config']['auto_theme']['latitude'], settings['ui_config']['auto_theme']['longitude'])
			settings['ui_config']['auto_theme']['sunrise'] = result['sunrise']
			settings['ui_config']['auto_theme']['sunset'] = result['sunset']
			settings['ui_config']['auto_theme']['lastupdate'] = result['lastupdate']
			WriteJSON(settings, 'settings')
			WriteLog('Sunrise/Sunset times have expired.  Updated sunrise/sunset times.')
		thememode = night_or_day(settings['ui_config']['auto_theme']['latitude'], settings['ui_config']['auto_theme']['longitude'])
		if(thememode == 'day'):
			theme = settings['ui_config']['auto_theme']['theme_day'] 
		else: 
			theme = settings['ui_config']['auto_theme']['theme_night']
	else:
		theme = settings['ui_config']['pagetheme']

	return(theme)

if __name__ == '__main__':
	if is_raspberrypi():
		app.run(host='0.0.0.0')
	else:
		app.run(host='0.0.0.0', debug=True)

