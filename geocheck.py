from geopy.geocoders import Nominatim  # pip3 install geopy
import datetime
from suntime import Sun  # pip3 install suntime
from common import WriteLog

def location_check(location):
	result = {}
	try:
		geolocator = Nominatim(user_agent="geocheck")
		details = geolocator.geocode(location)
		lat = details.latitude
		long = details.longitude

		result['success'] = True
		result['latitude'] = lat 
		result['longitude'] = long 
		result['location'] = location 
	except:
		# If any error occurred, return false
		result['success'] = False
		WriteLog('Location Check Failed.')

	return(result)

def get_sunrise_sunset(lat, long):
	result = {}
	try:
		sun = Sun(lat, long)
		# Get today's sunrise and sunset
		today_sr = sun.get_local_sunrise_time()
		today_ss = sun.get_local_sunset_time()

		result['success'] = True
		result['latitude'] = lat 
		result['longitude'] = long 
		result['sunrise'] = today_sr.time().strftime('%H:%M')
		result['sunset'] = today_ss.time().strftime('%H:%M')
		result['lastupdate'] = datetime.datetime.now().strftime('%Y-%m-%d')
	except:
		# If any error occurred, return false
		result['success'] = False 
		WriteLog('Error occurred getting sunrise/sunset.')

	return(result)

def night_or_day(lat, long):
	sun = Sun(lat, long)

	# Get today's sunrise and sunset in UTC
	today_sr = sun.get_local_sunrise_time()
	today_ss = sun.get_local_sunset_time()

	now = datetime.datetime.now(today_sr.tzinfo)

	if (now.time() > today_sr.time()) and (now.time() < today_ss.time()):
		return('day')
	elif (now.time() < today_sr.time()) or (now.time() > today_ss.time()):
		return('night')
	else: 
		return(None)

def is_current(lastcheck):
	now = datetime.datetime.now()
	lc = datetime.datetime.strptime(lastcheck, '%Y-%m-%d')
	delta = datetime.timedelta(5)
	check = now - delta 
	
	if(lc.date() > check.date()):
		return(True)  # Current sunrise/sunset checked in last 5 days
	else:
		return(False)  # Current sunrise/sunset is older than 5 days
