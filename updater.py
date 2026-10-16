"""
 *****************************************
  Speaker Select Updater
 *****************************************

	Description: Version handling and git based update logic.
	Versions follow YYYY.MM.BuildNumber and are defined in version.json.
	Each entry in "upgrade_info" describes what is needed when upgrading
	to that version: "pip_install" (new python dependencies) and
	"reboot" (full reboot instead of restarting supervisor programs).

 *****************************************
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_FILE = 'version.json'
REQUIREMENTS = os.path.join(BASE_DIR, 'auto-install', 'requirements.txt')
SUPERVISOR_PROGRAMS = ['control', 'webapp']
MAX_COMMITS = 25

_lock = threading.Lock()
_state = {'running': False, 'done': False, 'success': False, 'progress': 0,
		  'step': '', 'output': [], 'action': None}


def parse_version(version):
	try:
		return tuple(int(p) for p in str(version).split('.'))
	except ValueError:
		return (0,)


def _git(*args, timeout=60):
	return subprocess.run(['git', '-C', BASE_DIR, *args], capture_output=True, text=True, timeout=timeout)


def read_manifest(text=None):
	try:
		if text is None:
			with open(os.path.join(BASE_DIR, MANIFEST_FILE)) as f:
				text = f.read()
		return json.loads(text)
	except (OSError, ValueError):
		return {}


def get_version():
	return read_manifest().get('version', 'unknown')


def _upstream():
	result = _git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}')
	if result.returncode == 0 and result.stdout.strip():
		return result.stdout.strip()
	branch = _git('rev-parse', '--abbrev-ref', 'HEAD').stdout.strip() or 'main'
	return f'origin/{branch}'


def upgrade_requirements(current, latest_manifest):
	'''Aggregate the upgrade requirements for every version after current, up to latest.'''
	need = {'pip_install': False, 'reboot': False, 'notes': []}
	latest = parse_version(latest_manifest.get('version'))
	for ver, info in latest_manifest.get('upgrade_info', {}).items():
		pv = parse_version(ver)
		if parse_version(current) < pv <= latest:
			need['pip_install'] |= bool(info.get('pip_install'))
			need['reboot'] |= bool(info.get('reboot'))
			if info.get('notes'):
				need['notes'].append(f"{ver}: {info['notes']}")
	return need


def check_for_update():
	'''Fetch from GitHub and compare versions. Returns a JSON friendly dict.'''
	current = get_version()
	result = {'success': False, 'current': current, 'latest': current, 'update_available': False,
			  'commits': [], 'pip_install': False, 'reboot': False, 'notes': [], 'error': ''}
	if not shutil.which('git') or not os.path.isdir(os.path.join(BASE_DIR, '.git')):
		result['error'] = 'This installation is not a git repository.'
		return result
	try:
		fetch = _git('fetch', 'origin', timeout=90)
		if fetch.returncode != 0:
			result['error'] = (fetch.stderr or fetch.stdout).strip() or 'git fetch failed.'
			return result
		upstream = _upstream()
		remote = read_manifest(_git('show', f'{upstream}:{MANIFEST_FILE}').stdout)
		result['latest'] = remote.get('version', current)
		log = _git('log', f'HEAD..{upstream}', f'--max-count={MAX_COMMITS}', '--pretty=format:%h%x1f%an%x1f%ad%x1f%s', '--date=short')
		for line in log.stdout.splitlines():
			parts = line.split('\x1f')
			if len(parts) == 4:
				result['commits'].append(dict(zip(('hash', 'author', 'date', 'subject'), parts)))
		ahead = _git('rev-list', '--count', f'HEAD..{upstream}').stdout.strip()
		behind_version = parse_version(result['latest']) > parse_version(current)
		result['update_available'] = behind_version or (ahead.isdigit() and int(ahead) > 0)
		need = upgrade_requirements(current, remote)
		result.update(pip_install=need['pip_install'], reboot=need['reboot'], notes=need['notes'])
		result['success'] = True
	except (subprocess.SubprocessError, OSError) as e:
		result['error'] = str(e)
	return result


def get_status():
	with _lock:
		return dict(_state, output=list(_state['output']))


def _emit(line):
	with _lock:
		_state['output'].append(line.rstrip('\n'))


def _step(progress, text):
	with _lock:
		_state['progress'] = progress
		_state['step'] = text
	_emit(f'--- {text}')


def _run(cmd, cwd=BASE_DIR):
	'''Run a command, streaming its output. Returns the exit code.'''
	_emit('$ ' + ' '.join(cmd))
	try:
		proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
		for line in proc.stdout:
			_emit(line)
		return proc.wait()
	except OSError as e:
		_emit(f'ERROR: {e}')
		return 1


def _finish(success):
	with _lock:
		_state.update(running=False, done=True, success=success)
		if success:
			_state['progress'] = 100


def _perform_update():
	try:
		before = get_version()
		_step(10, 'Checking for updates')
		info = check_for_update()
		if not info['success']:
			_emit('ERROR: ' + info['error'])
			return _finish(False)
		_step(30, 'Pulling update from GitHub')
		if _run(['git', 'pull', '--ff-only']) != 0:
			_emit('ERROR: git pull failed. Local changes may conflict with the update.')
			return _finish(False)
		if info['pip_install']:
			_step(55, 'Installing new Python dependencies')
			if _run([sys.executable, '-m', 'pip', 'install', '-r', REQUIREMENTS]) != 0:
				_emit('ERROR: dependency installation failed.')
				return _finish(False)
		after = get_version()
		_emit(f'Updated from {before} to {after}.')
		action = 'reboot' if info['reboot'] else 'restart'
		with _lock:
			_state['action'] = action
		_step(80, 'Rebooting system' if action == 'reboot' else 'Restarting services')
		_finish(True)
		_apply(action)
	except Exception as e:
		_emit(f'ERROR: {e}')
		_finish(False)


def _apply(action):
	'''Detached so the command survives this process being stopped.'''
	if action == 'reboot':
		reboot = shutil.which('reboot')
		if not reboot:
			_emit('ERROR: reboot command not found. Please reboot manually.')
			return
		cmd = f'sleep 3; sudo -n {reboot}'
	else:
		sup = shutil.which('supervisorctl') or '/usr/bin/supervisorctl'
		progs = ' '.join(SUPERVISOR_PROGRAMS)
		cmd = f'sleep 3; sudo -n {sup} restart {progs} || {sup} restart {progs}'
	subprocess.Popen(['sh', '-c', cmd], start_new_session=True,
					 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_update():
	'''Start the update in the background. Returns False if one is already running.'''
	with _lock:
		if _state['running']:
			return False
		_state.update(running=True, done=False, success=False, progress=0, step='', output=[], action=None)
	threading.Thread(target=_perform_update, daemon=True).start()
	return True
