#!/usr/bin/env python3
"""Server infrastructure: dependency checking, SSL, storage secrets, temp cleanup."""

import os
import tempfile
from pathlib import Path

from ..engine import log
import contextlib

# Auto-install required packages

def ensure_requirements() -> dict:
    """Check all required packages and install missing ones via pip.

    Returns a dict with keys: found, optional_found, optional_missing, missing_installed.
    Caller is responsible for logging the results after the logging system is ready.
    """
    import importlib
    import subprocess
    import sys

    _REQUIRED = {
        "anthropic":      "anthropic",
        "openai":         "openai",
        "nicegui":        "nicegui",
        "cryptography":   "cryptography",
        "yaml":           "PyYAML",
    }
    _OPTIONAL: dict[str, str] = {}

    print("\u2699\uFE0F  Checking dependencies ...")

    found = []
    missing = []
    for import_name, pip_name in _REQUIRED.items():
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", getattr(mod, "VERSION", ""))
            ver_str = f" ({ver})" if ver else ""
            found.append(f"{pip_name}{ver_str}")
        except ImportError:
            missing.append(pip_name)

    optional_found = []
    optional_missing = []
    for import_name, pip_name in _OPTIONAL.items():
        try:
            mod = importlib.import_module(import_name)
            ver = getattr(mod, "__version__", getattr(mod, "VERSION", ""))
            ver_str = f" ({ver})" if ver else ""
            optional_found.append(f"{pip_name}{ver_str}")
        except ImportError:
            optional_missing.append(pip_name)

    if found:
        print(f"   \u2705 Found: {', '.join(found)}")
    if optional_found:
        print(f"   \u2705 Optional: {', '.join(optional_found)}")
    if optional_missing:
        print(f"   \u2139\uFE0F  Optional (not installed): {', '.join(optional_missing)}")
    if missing:
        print(f"   \u274C Missing: {', '.join(missing)}")

    missing_installed = []
    if missing:
        print(f"\n   \u2B07\uFE0F  Installing: {', '.join(missing)} ...")
        pip_cmd = [sys.executable, "-m", "pip", "install", *missing]
        try:
            subprocess.check_call(pip_cmd)
            missing_installed = list(missing)
        except subprocess.CalledProcessError:
            try:
                subprocess.check_call(pip_cmd + ["--break-system-packages"])
                missing_installed = list(missing)
            except subprocess.CalledProcessError as e:
                print(f"   \u274C pip install failed: {e}")

    return {
        "found": found,
        "optional_found": optional_found,
        "optional_missing": optional_missing,
        "missing_installed": missing_installed,
    }

# Server config loading

def load_server_config() -> dict:
    """Load server configuration with cascade: config.yaml -> ENV override -> defaults."""
    from ..engine import load_global_config

    cfg = {
        "api_key": "",
        "invite_code": "",
        "enable_https": False,
        "ssl_certfile": "",
        "ssl_keyfile": "",
        "storage_secret": "",
        "port": 8080,
    }
    file_cfg = load_global_config()
    for key in cfg:
        if key in file_cfg:
            cfg[key] = file_cfg[key]

    env_map = {
        "INVITE_CODE": "invite_code",
        "ENABLE_HTTPS": "enable_https",
        "SSL_CERTFILE": "ssl_certfile",
        "SSL_KEYFILE": "ssl_keyfile",
        "STORAGE_SECRET": "storage_secret",
        "PORT": "port",
    }
    # API key env override: use the config-driven env var name (ai.api_key_env)
    from ..engine.config_loader import cfg as _cfg
    _api_key_env = _cfg().ai.api_key_env
    api_key_from_env = os.environ.get(_api_key_env, "").strip()
    if api_key_from_env and not cfg["api_key"]:
        cfg["api_key"] = api_key_from_env
    for env_key, cfg_key in env_map.items():
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            if cfg_key == "enable_https":
                cfg[cfg_key] = env_val.lower() in ("1", "true", "yes")
            elif cfg_key == "port":
                with contextlib.suppress(ValueError):
                    cfg[cfg_key] = int(env_val)
            else:
                cfg[cfg_key] = env_val
    return cfg

# SSL

def generate_self_signed_cert():
    """Generate a self-signed SSL certificate for local HTTPS."""
    cert_dir = Path.home() / ".rpg_engine_ssl"
    cert_dir.mkdir(exist_ok=True)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"
    if cert_path.exists() and key_path.exists():
        import time
        age_days = (time.time() - cert_path.stat().st_mtime) / 86400
        if age_days < 365:
            log(f"[SSL] Reusing existing certificate from {cert_dir}")
            return str(cert_path), str(key_path)
    try:
        import datetime
        import ipaddress
        import socket

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        log("[SSL] Generating self-signed certificate...")
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        hostname = socket.gethostname()
        san_entries = [
            x509.DNSName("localhost"),
            x509.DNSName(hostname),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        try:
            for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
                ip = info[4][0]
                if ip != "127.0.0.1":
                    san_entries.append(x509.IPAddress(ipaddress.IPv4Address(ip)))
        except Exception:
            pass
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, "Straightjacket Local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Straightjacket"),
        ])
        cert = (x509.CertificateBuilder()
                .subject_name(subject).issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.now(datetime.UTC))
                .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=365))
                .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
                .sign(key, hashes.SHA256()))
        key_path.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        log(f"[SSL] Certificate generated: {cert_path}")
        log(f"[SSL] SAN entries: {[str(s) for s in san_entries]}")
        return str(cert_path), str(key_path)
    except ImportError:
        log("[SSL] 'cryptography' package not installed. Run: pip install cryptography", level="warning")
        return None, None
    except Exception as e:
        log(f"[SSL] Certificate generation failed: {e}", level="warning")
        return None, None

# Storage secret

def get_storage_secret(server_cfg: dict) -> str:
    """Get storage secret: from ENV / config.yaml, or generate and persist one."""
    if server_cfg.get("storage_secret"):
        return server_cfg["storage_secret"]
    secret_file = Path(__file__).resolve().parent.parent.parent.parent / ".storage_secret"
    if secret_file.exists():
        try:
            return secret_file.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    import secrets
    new_secret = secrets.token_urlsafe(32)
    try:
        secret_file.write_text(new_secret, encoding="utf-8")
        try:
            import stat
            secret_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        log(f"[Security] Generated new storage secret -> {secret_file}")
    except OSError:
        log("[Security] Could not persist storage secret — using ephemeral", level="warning")
    return new_secret

# Touch icon generation

def generate_touch_icon() -> Path:
    """Create a minimal 180x180 PNG apple-touch-icon with the accent color."""
    import struct
    import zlib
    size = 180
    r, g, b = 0xD9, 0x77, 0x06
    raw = b''
    for _ in range(size):
        raw += b'\x00' + bytes([r, g, b]) * size
    def _chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
    png = (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
           + _chunk(b'IDAT', zlib.compress(raw)) + _chunk(b'IEND', b''))
    icon_path = Path(tempfile.gettempdir()) / "rpg_touch_icon.png"
    icon_path.write_bytes(png)
    return icon_path
