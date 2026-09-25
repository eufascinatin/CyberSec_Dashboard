import hashlib
import secrets
import base64

PBKDF2_ITERATIONS = 100_000

def encrypt_password(password: str) -> str:
    if not password:
        return password
    key = "ODT_SECRET_KEY"
    encrypted = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(password))
    return base64.b64encode(encrypted.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_b64: str) -> str:
    if not encrypted_b64:
        return encrypted_b64
    try:
        encrypted = base64.b64decode(encrypted_b64.encode('utf-8')).decode('utf-8')
        key = "ODT_SECRET_KEY"
        return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(encrypted))
    except Exception:
        return encrypted_b64


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return f"{salt}${pwd_hash}"

def verify_password(password, stored_hash):
    if not stored_hash:
        return False
    if '$' in stored_hash:
        salt, _ = stored_hash.split('$', 1)
        return hash_password(password, salt) == stored_hash
    # Legacy unsalted sha256 hash from before the salted-hashing migration.
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash
