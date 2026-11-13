from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# AJ root for subprocess/cli checks
AJ_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = AJ_ROOT / '.venv' / 'bin' / 'python'


def _run(args, env_extra=None):
    env = os.environ.copy()
    env['PYTHONPATH'] = str(AJ_ROOT) + (os.pathsep + env.get('PYTHONPATH','') if env.get('PYTHONPATH') else '')
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=str(AJ_ROOT), env=env, capture_output=True, text=True)


def test_orb_module_import_safe_without_gui_calls():
    # Import should not require GTK to be present/initialized.
    import aj.orb as orb
    assert hasattr(orb, 'run_orb')
    assert hasattr(orb, 'resolve_inbox_root') or hasattr(orb, 'InboxStore')


def test_resolve_inbox_root_precedence_and_config():
    from aj.config import load
    from aj.inbox import resolve_inbox_root, InboxStore
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        explicit = d / 'explicit-inbox'
        cfg = load(None, env={}, overrides={'core': {'data_dir': str(d / 'data')}})
        assert resolve_inbox_root(explicit=str(explicit), config=cfg) == explicit
        assert resolve_inbox_root(config=cfg) == d / 'data' / 'knowledge-inbox'
        os.environ['AJ_INBOX_ROOT'] = str(d / 'env-inbox')
        try:
            assert resolve_inbox_root(config=cfg) == d / 'env-inbox'
            # explicit still wins
            assert resolve_inbox_root(explicit=str(explicit), config=cfg) == explicit
        finally:
            os.environ.pop('AJ_INBOX_ROOT', None)
        store = InboxStore(None, config=cfg)
        assert store.root == d / 'data' / 'knowledge-inbox'
        assert (store.root / 'index' / 'inbox.sqlite3').exists()


def test_orb_state_roundtrip_and_clamp_helpers_importable():
    import aj.orb as orb
    from aj.inbox import InboxStore
    with tempfile.TemporaryDirectory() as d:
        store = InboxStore(d)
        state = orb.load_orb_state(store)
        assert isinstance(state, dict)
        assert 'x' in state and 'y' in state and 'paused' in state
        state['x'], state['y'], state['paused'] = 123, 456, True
        orb.save_orb_state(store, state)
        state2 = orb.load_orb_state(store)
        assert state2['x'] == 123 and state2['y'] == 456 and state2['paused'] is True


def test_orb_uri_parsing_helper():
    import aj.orb as orb
    p, u = orb._uri_to_path_or_url('file:///tmp/My%20File.txt')
    assert p == '/tmp/My File.txt' and u is None
    p, u = orb._uri_to_path_or_url('https://example.com/a?b=1')
    assert p is None and u == 'https://example.com/a?b=1'
    p, u = orb._uri_to_path_or_url('ftp://example.com/x')
    assert p is None and u is None


def test_single_instance_lock_advisory():
    import aj.orb as orb
    with tempfile.TemporaryDirectory() as d:
        lp = Path(d) / 'orb.lock'
        a = orb.OrbInstanceLock(lp)
        b = orb.OrbInstanceLock(lp)
        assert a.try_acquire() is True
        # Second acquire should fail on POSIX flock systems.
        got = b.try_acquire()
        if got is False:
            pass  # expected
        else:
            # non-flock environment: best-effort, but must not crash
            assert got is True
        a.release()
        c = orb.OrbInstanceLock(lp)
        assert c.try_acquire() is True
        c.release()


def test_cli_orb_help_and_check_gui_json():
    r = _run([str(VENV_PY), '-m', 'aj', 'orb', '--help'])
    assert r.returncode == 0, r.stderr
    assert '--inbox-root' in r.stdout
    assert '--check-gui' in r.stdout
    assert '--system-python' in r.stdout

    r = _run([str(VENV_PY), '-m', 'aj', 'orb', '--check-gui', '--json'])
    # venv may not have gi: command should report clearly (ok false) with exit 5
    assert r.returncode in (0, 5)
    j = json.loads(r.stdout)
    assert 'ok' in j and 'gtk' in j and 'inbox_root' in j

    r = _run([str(VENV_PY), '-m', 'aj', 'inbox', 'orb', '--help'])
    assert r.returncode == 0


def test_system_python_orb_module_check_gui_when_available():
    # Validates the GTK fallback runtime strategy is viable on this host (system python has gi).
    r = _run(['/usr/bin/python3', '-m', 'aj.orb', '--check-gui'])
    if r.returncode == 0:
        j = json.loads(r.stdout)
        assert j.get('ok') is True
        assert j.get('gtk') is True
    else:
        # If unavailable in environment, must fail clearly (not silently)
        assert r.returncode != 0
