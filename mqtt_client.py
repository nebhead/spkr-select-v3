"""
 *****************************************
  Speaker Select MQTT Bridge
 *****************************************

	Description: Optional MQTT support with Home Assistant auto-discovery.
	Runs inside the control process.  paho-mqtt's network loop runs in its
	own background thread, so the control loop is never blocked: inbound
	commands are queued and applied by the control loop, and state is only
	published when it actually changes (retained, so no periodic traffic).

 *****************************************
"""

import json
import queue
import re
import socket
import threading

from common import WriteLog

try:
	import paho.mqtt.client as mqtt
except ImportError:  # Optional dependency; the rest of the app keeps working
	mqtt = None

ON, OFF = 'ON', 'OFF'


def _slug(text):
	return re.sub(r'[^a-z0-9_]+', '_', str(text).lower()).strip('_') or 'spkr_select'


class MqttBridge:
	def __init__(self, settings):
		self.commands = queue.Queue()
		self.client = None
		self.connected = False
		self._lock = threading.Lock()
		self._conn_key = None
		self._last_published = None
		self._cfg = {}
		self._settings = settings
		self._spkr_state = {}
		self.configure(settings)

	# ---------- configuration ----------

	def _topics(self):
		base = self._cfg['base_topic'].strip('/')
		return base, f'{base}/status'

	def configure(self, settings):
		"""Apply (possibly changed) settings. Reconnects only if connection details changed."""
		self._settings = settings
		cfg = settings.get('mqtt_config', {})
		self._cfg = {
			'enabled': bool(cfg.get('enabled')),
			'host': str(cfg.get('host', '')).strip(),
			'port': int(cfg.get('port', 1883) or 1883),
			'username': cfg.get('username', ''),
			'password': cfg.get('password', ''),
			'base_topic': cfg.get('base_topic') or 'spkr-select',
			'discovery_prefix': (cfg.get('discovery_prefix') or 'homeassistant').strip('/'),
			'device_id': _slug(cfg.get('device_id') or socket.gethostname()),
		}
		if not (self._cfg['enabled'] and self._cfg['host']):
			self._stop()
			return
		if mqtt is None:
			WriteLog('MQTT enabled but paho-mqtt is not installed.', logger_name='control')
			return

		conn_key = tuple(self._cfg[k] for k in ('host', 'port', 'username', 'password', 'base_topic', 'discovery_prefix', 'device_id'))
		if self.client is not None and conn_key == self._conn_key:
			if self.connected:
				self._publish_discovery()  # Names / enabled speakers may have changed
				self._last_published = None
			return
		self._stop()
		self._start(conn_key)

	def _start(self, conn_key):
		self._conn_key = conn_key
		cfg = self._cfg
		client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"spkr-select-{cfg['device_id']}")
		if cfg['username']:
			client.username_pw_set(cfg['username'], cfg['password'] or None)
		_, status_topic = self._topics()
		client.will_set(status_topic, OFF.lower(), qos=1, retain=True)
		client.reconnect_delay_set(min_delay=5, max_delay=120)  # Back off when broker is down
		client.on_connect = self._on_connect
		client.on_disconnect = self._on_disconnect
		client.on_message = self._on_message
		self.client = client
		try:
			client.connect_async(cfg['host'], cfg['port'], keepalive=60)
			client.loop_start()
			WriteLog(f"MQTT connecting to {cfg['host']}:{cfg['port']}", logger_name='control')
		except Exception as e:
			WriteLog(f'MQTT start failed: {e}', logger_name='control')

	def _stop(self):
		client, self.client = self.client, None
		self.connected = False
		self._conn_key = None
		self._last_published = None
		if client:
			try:
				_, status_topic = self._topics()
				client.publish(status_topic, OFF.lower(), qos=1, retain=True)
				client.disconnect()
				client.loop_stop()
			except Exception:
				pass

	# ---------- paho callbacks (run in paho's thread) ----------

	def _on_connect(self, client, userdata, flags, reason_code, properties=None):
		if reason_code != 0:
			WriteLog(f'MQTT connection refused: {reason_code}', logger_name='control')
			return
		base, status_topic = self._topics()
		client.subscribe([(f'{base}/+/set', 1), (f"{self._cfg['discovery_prefix']}/status", 0)])
		client.publish(status_topic, 'online', qos=1, retain=True)
		self.connected = True
		self._publish_discovery()
		self._last_published = None  # Force a state publish from the control loop
		WriteLog('MQTT connected.', logger_name='control')

	def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
		self.connected = False

	def _on_message(self, client, userdata, msg):
		topic = msg.topic
		payload = msg.payload.decode('utf-8', 'ignore').strip().upper()
		if topic == f"{self._cfg['discovery_prefix']}/status":
			if payload == 'ONLINE':  # Home Assistant restarted
				self._publish_discovery()
				self._last_published = None
			return
		base, _ = self._topics()
		parts = topic[len(base) + 1:].split('/')
		if len(parts) == 2 and parts[1] == 'set' and payload in (ON, OFF):
			self.commands.put((parts[0], payload.lower()))

	# ---------- publishing ----------

	def _device(self):
		return {
			'identifiers': [f"spkr_select_{self._cfg['device_id']}"],
			'name': 'Speaker Select',
			'manufacturer': 'nebhead',
			'model': 'Speaker Select v3',
		}

	def _publish_discovery(self):
		if not self.client:
			return
		base, status_topic = self._topics()
		prefix, dev = self._cfg['discovery_prefix'], self._cfg['device_id']
		common = {'availability_topic': status_topic, 'payload_available': 'online',
				  'payload_not_available': 'offline', 'device': self._device()}

		for key, spkr in self._settings['spkr_config'].items():
			topic = f'{prefix}/switch/{dev}/{key}/config'
			if spkr.get('enabled'):
				payload = dict(common, name=spkr['name'], unique_id=f'{dev}_{key}',
							   state_topic=f'{base}/{key}/state', command_topic=f'{base}/{key}/set',
							   payload_on=ON, payload_off=OFF, icon='mdi:speaker')
				self.client.publish(topic, json.dumps(payload), qos=1, retain=True)
			else:
				self.client.publish(topic, '', qos=1, retain=True)  # Remove from HA

		pro = self._settings.get('protection', {})
		payload = dict(common, name=pro.get('name', 'Speaker Protection'), unique_id=f'{dev}_spkr_pro',
					   state_topic=f'{base}/spkr_pro/state', payload_on=ON, payload_off=OFF,
					   device_class='running', entity_category='diagnostic')
		self.client.publish(f'{prefix}/binary_sensor/{dev}/spkr_pro/config', json.dumps(payload), qos=1, retain=True)

	def publish_states(self, spkr_state):
		"""Cheap no-op unless the state changed (or a (re)connect needs a full refresh)."""
		if not self.connected or spkr_state == self._last_published:
			return
		base, _ = self._topics()
		prev = self._last_published or {}
		for key, value in spkr_state.items():
			if prev.get(key) != value:
				self.client.publish(f'{base}/{key}/state', ON if value == 'on' else OFF, qos=1, retain=True)
		self._last_published = spkr_state.copy()

	# ---------- control loop hook ----------

	def process(self, platform):
		"""Called from the control loop: apply queued commands, then publish changes."""
		if self.client is None:
			return
		changed = False
		while not self.commands.empty():
			key, value = self.commands.get_nowait()
			spkr = self._settings['spkr_config'].get(key)
			if spkr and spkr.get('enabled') and platform.spkr_state.get(key) != value:
				platform.spkr_state[key] = value
				changed = True
		if changed:
			platform.set_relays()
		self.publish_states(platform.spkr_state)
