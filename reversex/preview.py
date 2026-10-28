"""Isolated preview policy for untrusted reconstructed apps.

A separate localhost port alone is NOT treated as a sandbox.
Executable preview is allowed only when a restricted Docker container is available
(no host secrets, no docker.sock, read-only app mount, internal network where possible).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


PREVIEW_PORT = 8002
CONTAINER_NAME = 'reversex-phase2-preview'
NETWORK_NAME = 'reversex-preview-internal'


def docker_daemon_available() -> tuple[bool, str]:
    if not shutil.which('docker'):
        return False, 'docker CLI not found'
    try:
        proc = subprocess.run(
            ['docker', 'info'],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'docker info failed: {exc}'
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip()[:240]
        return False, f'docker daemon unavailable: {err}'
    return True, 'docker daemon reachable'


def _ensure_internal_network() -> tuple[bool, str]:
    """Create an internal Docker network (no outbound to other networks)."""
    inspect = subprocess.run(
        ['docker', 'network', 'inspect', NETWORK_NAME],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if inspect.returncode == 0:
        return True, 'network exists'
    created = subprocess.run(
        ['docker', 'network', 'create', '--internal', NETWORK_NAME],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if created.returncode != 0:
        return False, (created.stderr or created.stdout or 'network create failed')[:240]
    return True, 'network created'


def stop_preview() -> dict:
    """Remove preview container if present. Does not remove the internal network."""
    proc = subprocess.run(
        ['docker', 'rm', '-f', CONTAINER_NAME],
        capture_output=True, text=True, timeout=30, check=False,
    )
    return {
        'removed': proc.returncode == 0 or 'No such container' in (proc.stderr or ''),
        'detail': ((proc.stdout or '') + (proc.stderr or ''))[:200],
    }


def preview_http_ready(timeout_s: float = 20.0) -> tuple[bool, str]:
    """Confirm the published loopback preview actually answers HTTP."""
    url = f'http://127.0.0.1:{PREVIEW_PORT}/'
    deadline = time.monotonic() + timeout_s
    last = 'not attempted'
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                code = getattr(resp, 'status', None) or resp.getcode()
                if code == 200:
                    return True, f'HTTP {code}'
                last = f'HTTP {code}'
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = str(exc)
        time.sleep(0.5)
    return False, last


def _run_nginx_container(*, network: str, reconstructed_dir: Path) -> subprocess.CompletedProcess:
    mount = f'{reconstructed_dir}:/usr/share/nginx/html:ro'
    cmd = [
        'docker', 'run', '-d',
        '--name', CONTAINER_NAME,
        '--read-only',
        '--tmpfs', '/var/cache/nginx:rw,noexec,nosuid,size=16m',
        '--tmpfs', '/var/run:rw,noexec,nosuid,size=8m',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=8m',
        '--cap-drop', 'ALL',
        '--cap-add', 'CHOWN',
        '--cap-add', 'SETUID',
        '--cap-add', 'SETGID',
        '--cap-add', 'NET_BIND_SERVICE',
        '--security-opt', 'no-new-privileges:true',
        '--memory', '128m',
        '--memory-swap', '128m',
        '--cpus', '0.50',
        '--pids-limit', '64',
        '--network', network,
        '-p', f'127.0.0.1:{PREVIEW_PORT}:80',
        '-v', mount,
        'nginx:alpine',
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=False)


def prepare_preview(reconstructed_dir: Path) -> dict:
    """Attempt restricted container preview; otherwise block execution."""
    reconstructed_dir = reconstructed_dir.resolve()
    required = ('index.html', 'style.css', 'script.js')
    missing = [name for name in required if not (reconstructed_dir / name).is_file()]
    if missing:
        return {
            'status': 'blocked',
            'reason': f'missing generated files: {missing}',
            'url': None,
            'isolation': 'none',
        }

    ok, detail = docker_daemon_available()
    if not ok:
        return {
            'status': 'blocked',
            'reason': (
                'Adequate isolation unavailable. '
                f'{detail}. '
                'Refusing to serve untrusted reconstructed JavaScript via bare host http.server. '
                'Files were saved for offline inspection and Phase 3 differential testing.'
            ),
            'url': None,
            'isolation': 'none',
            'files_ready': True,
            'suggested_url_if_isolated': f'http://127.0.0.1:{PREVIEW_PORT}/',
        }

    net_ok, net_detail = _ensure_internal_network()
    if not net_ok:
        return {
            'status': 'blocked',
            'reason': f'could not create internal docker network: {net_detail}',
            'url': None,
            'isolation': 'docker_attempted',
            'files_ready': True,
        }

    stop_preview()
    # Mount ONLY the reconstructed-app directory read-only. Never mount .env, repo root, or docker.sock.
    proc = _run_nginx_container(network=NETWORK_NAME, reconstructed_dir=reconstructed_dir)
    isolation_mode = 'docker_nginx_readonly_internal'
    reason = (
        'Serving reconstructed app in read-only nginx on an internal Docker network. '
        'No .env, no docker.sock, no privileged mode, loopback publish only.'
    )
    limitations = [
        'Treat generated JS as untrusted; browser allowlist still required.',
        'This is stronger than bare host http.server but not a full OS sandbox.',
    ]

    need_bridge = proc.returncode != 0
    if not need_bridge:
        ready, ready_detail = preview_http_ready(timeout_s=12.0)
        if not ready:
            need_bridge = True
            stop_preview()
            limitations.append(
                f'Internal network container started but loopback HTTP not ready ({ready_detail}); '
                'falling back to bridge with the same filesystem/capability restrictions.'
            )

    if need_bridge:
        stop_preview()
        proc2 = _run_nginx_container(network='bridge', reconstructed_dir=reconstructed_dir)
        if proc2.returncode != 0:
            return {
                'status': 'blocked',
                'reason': (
                    f'docker run failed (internal): {(proc.stderr or proc.stdout)[:200]}; '
                    f'bridge fallback: {(proc2.stderr or proc2.stdout)[:200]}'
                ),
                'url': None,
                'isolation': 'docker_attempted',
                'files_ready': True,
            }
        ready, ready_detail = preview_http_ready(timeout_s=20.0)
        if not ready:
            stop_preview()
            return {
                'status': 'blocked',
                'reason': f'preview container running but HTTP not reachable: {ready_detail}',
                'url': None,
                'isolation': 'docker_attempted',
                'files_ready': True,
            }
        isolation_mode = 'docker_nginx_readonly_bridge'
        reason = (
            'Serving reconstructed app in read-only nginx container (bridge). '
            'No .env, no docker.sock, loopback bind only.'
        )
        limitations.extend([
            'Bridge network may allow container DNS/outbound; browser request filtering is mandatory.',
            'Not a full browser/OS exploit sandbox.',
        ])
    else:
        # Already confirmed HTTP ready on internal path.
        pass

    return {
        'status': 'running',
        'reason': reason,
        'url': f'http://127.0.0.1:{PREVIEW_PORT}/',
        'isolation': isolation_mode,
        'container': CONTAINER_NAME,
        'network': NETWORK_NAME if isolation_mode.endswith('internal') else 'bridge',
        'files_ready': True,
        'limitations': limitations,
    }


def write_preview_status(output_dir: Path, preview: dict) -> Path:
    path = output_dir / 'preview_status.json'
    path.write_text(json.dumps(preview, indent=2), encoding='utf-8')
    return path
