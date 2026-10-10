from cryptography.fernet import Fernet

from .config import KEY_FILE

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not KEY_FILE.exists():
            KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            KEY_FILE.write_bytes(Fernet.generate_key())
        _fernet = Fernet(KEY_FILE.read_bytes().strip())
    return _fernet


def encrypt(text: str) -> str:
    if not text:
        return ""
    return _get_fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()
