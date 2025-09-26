import os
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from gi.repository import GObject, Gio, GLib

class SignatureStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    MISSING = "missing"
    UNKNOWN = "unknown"
    ERROR = "error"

class KeyTrust(Enum):
    UNDEFINED = "undefined"
    NEVER = "never"
    MARGINAL = "marginal"
    FULL = "full"
    ULTIMATE = "ultimate"
    UNKNOWN = "unknown"

@dataclass
class GpgKey:
    key_id: str
    fingerprint: str
    user_id: str
    email: str
    creation_date: datetime
    expiration_date: Optional[datetime]
    trust_level: KeyTrust
    key_size: int
    algorithm: str
    is_expired: bool
    is_revoked: bool
    subkeys: List[str]

@dataclass
class SignatureInfo:
    status: SignatureStatus
    key_id: str
    signer: str
    timestamp: datetime
    fingerprint: str
    trust_level: KeyTrust
    error_message: Optional[str]
    signature_file: Optional[str]

class SignatureVerificationResult(NamedTuple):
    verified: bool
    signature_info: Optional[SignatureInfo]
    key_info: Optional[GpgKey]
    warnings: List[str]
    errors: List[str]

class SignatureVerifier(GObject.Object):
    __gsignals__ = {
        'verification-started': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'verification-completed': (GObject.SignalFlags.RUN_LAST, None, (str, bool)),
        'key-imported': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'key-deleted': (GObject.SignalFlags.RUN_LAST, None, (str,)),
        'keyring-updated': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, gnupg_home: Optional[str] = None):
        super().__init__()
        self.gnupg_home = gnupg_home or os.path.expanduser("~/.gnupg")
        self.trusted_keys_cache = {}
        self.signature_cache = {}
        self.cache_timeout = 3600
        self.keyserver_urls = [
            "hkps://keys.openpgp.org",
            "hkps://keyserver.ubuntu.com",
            "hkps://pgp.mit.edu"
        ]
        
        self._ensure_gnupg_directory()
        self._configure_gpg_agent()

    def _ensure_gnupg_directory(self):
        Path(self.gnupg_home).mkdir(mode=0o700, parents=True, exist_ok=True)
        
        gpg_conf = Path(self.gnupg_home) / "gpg.conf"
        if not gpg_conf.exists():
            with open(gpg_conf, 'w') as f:
                f.write("keyserver hkps://keys.openpgp.org\n")
                f.write("keyserver-options auto-key-retrieve\n")
                f.write("trust-model tofu+pgp\n")
                f.write("no-greeting\n")
                f.write("no-permission-warning\n")

    def _configure_gpg_agent(self):
        agent_conf = Path(self.gnupg_home) / "gpg-agent.conf"
        if not agent_conf.exists():
            with open(agent_conf, 'w') as f:
                f.write("default-cache-ttl 28800\n")
                f.write("max-cache-ttl 86400\n")
                f.write("pinentry-program /usr/bin/pinentry-gtk2\n")

    def _run_gpg_command(self, args: List[str], input_data: Optional[bytes] = None) -> Tuple[int, str, str]:
        cmd = [
            "gpg",
            "--homedir", self.gnupg_home,
            "--batch",
            "--no-tty",
            "--quiet"
        ] + args
        
        try:
            result = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                timeout=30
            )
            return result.returncode, result.stdout.decode('utf-8', errors='ignore'), result.stderr.decode('utf-8', errors='ignore')
        except subprocess.TimeoutExpired:
            return -1, "", "GPG command timed out"
        except Exception as e:
            return -1, "", str(e)

    def verify_file_signature(self, file_path: str, signature_path: Optional[str] = None) -> SignatureVerificationResult:
        self.emit('verification-started', file_path)
        
        cache_key = f"{file_path}:{signature_path or ''}"
        if cache_key in self.signature_cache:
            cache_entry = self.signature_cache[cache_key]
            if datetime.now() - cache_entry['timestamp'] < timedelta(seconds=self.cache_timeout):
                return cache_entry['result']
        
        try:
            if signature_path:
                return self._verify_detached_signature(file_path, signature_path)
            else:
                return self._verify_inline_signature(file_path)
        except Exception as e:
            result = SignatureVerificationResult(
                verified=False,
                signature_info=None,
                key_info=None,
                warnings=[],
                errors=[str(e)]
            )
            self.emit('verification-completed', file_path, False)
            return result

    def _verify_detached_signature(self, file_path: str, signature_path: str) -> SignatureVerificationResult:
        returncode, stdout, stderr = self._run_gpg_command([
            "--verify",
            "--status-fd", "1",
            signature_path,
            file_path
        ])
        
        return self._parse_verification_output(returncode, stdout, stderr, signature_path)

    def _verify_inline_signature(self, file_path: str) -> SignatureVerificationResult:
        returncode, stdout, stderr = self._run_gpg_command([
            "--verify",
            "--status-fd", "1",
            file_path
        ])
        
        return self._parse_verification_output(returncode, stdout, stderr, file_path)

    def _parse_verification_output(self, returncode: int, stdout: str, stderr: str, signature_file: str) -> SignatureVerificationResult:
        warnings = []
        errors = []
        signature_info = None
        key_info = None
        verified = False
        
        for line in stdout.split('\n'):
            if line.startswith('[GNUPG:] GOODSIG'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    key_id = parts[2]
                    signer = parts[3]
                    signature_info = SignatureInfo(
                        status=SignatureStatus.VALID,
                        key_id=key_id,
                        signer=signer,
                        timestamp=datetime.now(),
                        fingerprint="",
                        trust_level=KeyTrust.UNKNOWN,
                        error_message=None,
                        signature_file=signature_file
                    )
                    verified = True
            
            elif line.startswith('[GNUPG:] BADSIG'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    key_id = parts[2]
                    signer = parts[3]
                    signature_info = SignatureInfo(
                        status=SignatureStatus.INVALID,
                        key_id=key_id,
                        signer=signer,
                        timestamp=datetime.now(),
                        fingerprint="",
                        trust_level=KeyTrust.UNKNOWN,
                        error_message="Bad signature",
                        signature_file=signature_file
                    )
            
            elif line.startswith('[GNUPG:] ERRSIG'):
                parts = line.split(' ')
                if len(parts) >= 3:
                    key_id = parts[2]
                    signature_info = SignatureInfo(
                        status=SignatureStatus.ERROR,
                        key_id=key_id,
                        signer="Unknown",
                        timestamp=datetime.now(),
                        fingerprint="",
                        trust_level=KeyTrust.UNKNOWN,
                        error_message="Signature error",
                        signature_file=signature_file
                    )
            
            elif line.startswith('[GNUPG:] NOSIG'):
                signature_info = SignatureInfo(
                    status=SignatureStatus.MISSING,
                    key_id="",
                    signer="",
                    timestamp=datetime.now(),
                    fingerprint="",
                    trust_level=KeyTrust.UNKNOWN,
                    error_message="No signature found",
                    signature_file=signature_file
                )
            
            elif line.startswith('[GNUPG:] EXPKEYSIG'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    key_id = parts[2]
                    signer = parts[3]
                    signature_info = SignatureInfo(
                        status=SignatureStatus.EXPIRED,
                        key_id=key_id,
                        signer=signer,
                        timestamp=datetime.now(),
                        fingerprint="",
                        trust_level=KeyTrust.UNKNOWN,
                        error_message="Expired key signature",
                        signature_file=signature_file
                    )
            
            elif line.startswith('[GNUPG:] REVKEYSIG'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    key_id = parts[2]
                    signer = parts[3]
                    signature_info = SignatureInfo(
                        status=SignatureStatus.REVOKED,
                        key_id=key_id,
                        signer=signer,
                        timestamp=datetime.now(),
                        fingerprint="",
                        trust_level=KeyTrust.UNKNOWN,
                        error_message="Revoked key signature",
                        signature_file=signature_file
                    )
        
        if signature_info and signature_info.key_id:
            key_info = self.get_key_info(signature_info.key_id)
        
        if stderr:
            if "No public key" in stderr:
                errors.append("Missing public key for verification")
            elif "BAD signature" in stderr:
                errors.append("Invalid signature detected")
            else:
                warnings.append(stderr.strip())
        
        result = SignatureVerificationResult(
            verified=verified,
            signature_info=signature_info,
            key_info=key_info,
            warnings=warnings,
            errors=errors
        )
        
        cache_key = f"{signature_file}:"
        self.signature_cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now()
        }
        
        self.emit('verification-completed', signature_file, verified)
        return result

    def get_key_info(self, key_id: str) -> Optional[GpgKey]:
        if key_id in self.trusted_keys_cache:
            return self.trusted_keys_cache[key_id]
        
        returncode, stdout, stderr = self._run_gpg_command([
            "--list-keys",
            "--with-colons",
            "--with-fingerprint",
            key_id
        ])
        
        if returncode != 0:
            return None
        
        return self._parse_key_info(stdout)

    def _parse_key_info(self, gpg_output: str) -> Optional[GpgKey]:
        lines = gpg_output.strip().split('\n')
        key_data = None
        fingerprint = ""
        user_id = ""
        email = ""
        subkeys = []
        
        for line in lines:
            fields = line.split(':')
            if len(fields) < 2:
                continue
            
            record_type = fields[0]
            
            if record_type == 'pub':
                if len(fields) >= 12:
                    trust = self._parse_trust_level(fields[1])
                    key_size = int(fields[2]) if fields[2] else 0
                    algorithm = fields[3]
                    key_id = fields[4]
                    creation_date = self._parse_date(fields[5])
                    expiration_date = self._parse_date(fields[6]) if fields[6] else None
                    is_expired = 'e' in fields[1]
                    is_revoked = 'r' in fields[1]
                    
                    key_data = {
                        'key_id': key_id,
                        'trust_level': trust,
                        'key_size': key_size,
                        'algorithm': algorithm,
                        'creation_date': creation_date,
                        'expiration_date': expiration_date,
                        'is_expired': is_expired,
                        'is_revoked': is_revoked
                    }
            
            elif record_type == 'fpr':
                if len(fields) >= 10:
                    fingerprint = fields[9]
            
            elif record_type == 'uid':
                if len(fields) >= 10:
                    uid_string = fields[9]
                    if '<' in uid_string and '>' in uid_string:
                        user_id = uid_string[:uid_string.find('<')].strip()
                        email = uid_string[uid_string.find('<')+1:uid_string.find('>')].strip()
                    else:
                        user_id = uid_string
            
            elif record_type == 'sub':
                if len(fields) >= 5:
                    subkeys.append(fields[4])
        
        if not key_data:
            return None
        
        gpg_key = GpgKey(
            key_id=key_data['key_id'],
            fingerprint=fingerprint,
            user_id=user_id,
            email=email,
            creation_date=key_data['creation_date'],
            expiration_date=key_data['expiration_date'],
            trust_level=key_data['trust_level'],
            key_size=key_data['key_size'],
            algorithm=key_data['algorithm'],
            is_expired=key_data['is_expired'],
            is_revoked=key_data['is_revoked'],
            subkeys=subkeys
        )
        
        self.trusted_keys_cache[key_data['key_id']] = gpg_key
        return gpg_key

    def _parse_trust_level(self, trust_char: str) -> KeyTrust:
        trust_map = {
            'o': KeyTrust.UNKNOWN,
            'i': KeyTrust.UNKNOWN,
            'd': KeyTrust.NEVER,
            'r': KeyTrust.UNKNOWN,
            'e': KeyTrust.UNKNOWN,
            '-': KeyTrust.UNDEFINED,
            'q': KeyTrust.UNDEFINED,
            'n': KeyTrust.NEVER,
            'm': KeyTrust.MARGINAL,
            'f': KeyTrust.FULL,
            'u': KeyTrust.ULTIMATE
        }
        return trust_map.get(trust_char.lower(), KeyTrust.UNKNOWN)

    def _parse_date(self, date_string: str) -> Optional[datetime]:
        if not date_string or date_string == '0':
            return None
        
        try:
            timestamp = int(date_string)
            return datetime.fromtimestamp(timestamp)
        except (ValueError, OSError):
            return None

    def list_keys(self, secret_keys: bool = False) -> List[GpgKey]:
        key_type = "--list-secret-keys" if secret_keys else "--list-keys"
        returncode, stdout, stderr = self._run_gpg_command([
            key_type,
            "--with-colons",
            "--with-fingerprint"
        ])
        
        if returncode != 0:
            return []
        
        keys = []
        current_key_lines = []
        
        for line in stdout.split('\n'):
            if line.startswith('pub:') and current_key_lines:
                key = self._parse_key_info('\n'.join(current_key_lines))
                if key:
                    keys.append(key)
                current_key_lines = []
            
            if line.strip():
                current_key_lines.append(line)
        
        if current_key_lines:
            key = self._parse_key_info('\n'.join(current_key_lines))
            if key:
                keys.append(key)
        
        return keys

    def import_key(self, key_data: bytes) -> Tuple[bool, str]:
        returncode, stdout, stderr = self._run_gpg_command(
            ["--import"],
            input_data=key_data
        )
        
        success = returncode == 0
        message = stdout if stdout else stderr
        
        if success:
            self.trusted_keys_cache.clear()
            self.emit('key-imported', message)
            self.emit('keyring-updated')
        
        return success, message

    def import_key_from_file(self, key_file_path: str) -> Tuple[bool, str]:
        try:
            with open(key_file_path, 'rb') as f:
                key_data = f.read()
            return self.import_key(key_data)
        except Exception as e:
            return False, str(e)

    def import_key_from_keyserver(self, key_id: str, keyserver: Optional[str] = None) -> Tuple[bool, str]:
        keyserver_arg = keyserver or self.keyserver_urls[0]
        
        returncode, stdout, stderr = self._run_gpg_command([
            "--keyserver", keyserver_arg,
            "--recv-keys", key_id
        ])
        
        success = returncode == 0
        message = stdout if stdout else stderr
        
        if success:
            self.trusted_keys_cache.clear()
            self.emit('key-imported', key_id)
            self.emit('keyring-updated')
        
        return success, message

    def delete_key(self, key_id: str, secret_key: bool = False) -> Tuple[bool, str]:
        if secret_key:
            returncode, stdout, stderr = self._run_gpg_command([
                "--yes",
                "--delete-secret-keys",
                key_id
            ])
            if returncode != 0:
                return False, stderr
        
        returncode, stdout, stderr = self._run_gpg_command([
            "--yes",
            "--delete-keys",
            key_id
        ])
        
        success = returncode == 0
        message = stdout if stdout else stderr
        
        if success:
            if key_id in self.trusted_keys_cache:
                del self.trusted_keys_cache[key_id]
            self.emit('key-deleted', key_id)
            self.emit('keyring-updated')
        
        return success, message

    def trust_key(self, key_id: str, trust_level: KeyTrust) -> Tuple[bool, str]:
        trust_values = {
            KeyTrust.NEVER: "2",
            KeyTrust.MARGINAL: "3",
            KeyTrust.FULL: "4",
            KeyTrust.ULTIMATE: "5"
        }
        
        trust_value = trust_values.get(trust_level)
        if not trust_value:
            return False, "Invalid trust level"
        
        edit_commands = f"{trust_value}\ny\nsave\n"
        
        returncode, stdout, stderr = self._run_gpg_command([
            "--command-fd", "0",
            "--edit-key", key_id,
            "trust"
        ], input_data=edit_commands.encode())
        
        success = returncode == 0
        message = stdout if stdout else stderr
        
        if success and key_id in self.trusted_keys_cache:
            self.trusted_keys_cache[key_id].trust_level = trust_level
        
        return success, message

    def export_key(self, key_id: str, armor: bool = True) -> Tuple[bool, bytes, str]:
        args = ["--export"]
        if armor:
            args.append("--armor")
        args.append(key_id)
        
        returncode, stdout, stderr = self._run_gpg_command(args)
        
        success = returncode == 0
        key_data = stdout.encode() if success else b""
        message = stderr
        
        return success, key_data, message

    def search_keys(self, search_term: str, keyserver: Optional[str] = None) -> List[Dict[str, str]]:
        keyserver_arg = keyserver or self.keyserver_urls[0]
        
        returncode, stdout, stderr = self._run_gpg_command([
            "--keyserver", keyserver_arg,
            "--search-keys", search_term
        ])
        
        if returncode != 0:
            return []
        
        keys = []
        current_key = {}
        
        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('('):
                if current_key:
                    keys.append(current_key)
                    current_key = {}
                current_key['index'] = line
            elif line.startswith('pub'):
                parts = line.split()
                if len(parts) >= 3:
                    current_key['key_id'] = parts[1].split('/')[-1]
                    current_key['created'] = parts[2] if len(parts) > 2 else ""
            elif line and not line.startswith('     '):
                current_key['user_id'] = line
        
        if current_key:
            keys.append(current_key)
        
        return keys

    def verify_package_signature(self, package_path: str) -> SignatureVerificationResult:
        sig_path = package_path + ".sig"
        if os.path.exists(sig_path):
            return self.verify_file_signature(package_path, sig_path)
        else:
            return SignatureVerificationResult(
                verified=False,
                signature_info=None,
                key_info=None,
                warnings=[],
                errors=["No signature file found"]
            )

    def verify_pkgbuild_signature(self, pkgbuild_path: str) -> SignatureVerificationResult:
        return self.verify_package_signature(pkgbuild_path)

    def get_trusted_keys(self) -> List[GpgKey]:
        trusted_keys = []
        all_keys = self.list_keys()
        
        for key in all_keys:
            if key.trust_level in [KeyTrust.FULL, KeyTrust.ULTIMATE, KeyTrust.MARGINAL]:
                trusted_keys.append(key)
        
        return trusted_keys

    def get_key_statistics(self) -> Dict[str, int]:
        keys = self.list_keys()
        stats = {
            'total': len(keys),
            'trusted': 0,
            'expired': 0,
            'revoked': 0,
            'rsa': 0,
            'dsa': 0,
            'ecdsa': 0,
            'eddsa': 0
        }
        
        for key in keys:
            if key.trust_level in [KeyTrust.FULL, KeyTrust.ULTIMATE, KeyTrust.MARGINAL]:
                stats['trusted'] += 1
            if key.is_expired:
                stats['expired'] += 1
            if key.is_revoked:
                stats['revoked'] += 1
            
            algorithm = key.algorithm.lower()
            if 'rsa' in algorithm:
                stats['rsa'] += 1
            elif 'dsa' in algorithm:
                stats['dsa'] += 1
            elif 'ecdsa' in algorithm:
                stats['ecdsa'] += 1
            elif 'eddsa' in algorithm or 'ed25519' in algorithm:
                stats['eddsa'] += 1
        
        return stats

    def cleanup_expired_keys(self) -> Tuple[int, List[str]]:
        keys = self.list_keys()
        expired_keys = [key for key in keys if key.is_expired]
        deleted_keys = []
        
        for key in expired_keys:
            success, message = self.delete_key(key.key_id)
            if success:
                deleted_keys.append(key.key_id)
        
        return len(deleted_keys), deleted_keys

    def backup_keyring(self, backup_path: str) -> bool:
        try:
            if os.path.exists(backup_path):
                shutil.rmtree(backup_path)
            shutil.copytree(self.gnupg_home, backup_path)
            return True
        except Exception:
            return False

    def restore_keyring(self, backup_path: str) -> bool:
        try:
            if os.path.exists(self.gnupg_home):
                shutil.rmtree(self.gnupg_home)
            shutil.copytree(backup_path, self.gnupg_home)
            self.trusted_keys_cache.clear()
            self.signature_cache.clear()
            self.emit('keyring-updated')
            return True
        except Exception:
            return False

    def clear_cache(self):
        self.trusted_keys_cache.clear()
        self.signature_cache.clear()

    def set_keyserver_urls(self, urls: List[str]):
        self.keyserver_urls = urls

    def get_keyserver_urls(self) -> List[str]:
        return self.keyserver_urls.copy()

    def validate_signature_format(self, signature_data: bytes) -> bool:
        try:
            signature_str = signature_data.decode('utf-8', errors='ignore')
            return (
                "-----BEGIN PGP SIGNATURE-----" in signature_str and
                "-----END PGP SIGNATURE-----" in signature_str
            )
        except Exception:
            return False

    def get_signature_algorithms(self) -> List[str]:
        return [
            "RSA",
            "DSA", 
            "ECDSA",
            "EdDSA",
            "RSA+SHA1",
            "RSA+SHA256",
            "RSA+SHA512",
            "ECDSA+SHA256",
            "ECDSA+SHA384",
            "EdDSA+SHA256"
        ]
