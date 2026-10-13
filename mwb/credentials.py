"""Secrets in Windows Credential Manager (design §16.3), through advapi32 with ctypes: no extra libraries.

Each secret is a generic credential, encrypted by Windows with your sign-in (DPAPI) and kept for this Windows
account on this laptop only. Control Panel > Credential Manager > Windows Credentials lists them under
"Generic Credentials" as MWB/api-key/<provider>. Nothing secret is ever written to a file."""
import ctypes, ctypes.wintypes as wt, datetime
from dataclasses import dataclass

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2      # this account on this laptop; ENTERPRISE (3) would roam with the profile
ERROR_NOT_FOUND = 1168


class CREDENTIAL(ctypes.Structure):
    _fields_ = [('Flags', wt.DWORD), ('Type', wt.DWORD), ('TargetName', wt.LPWSTR), ('Comment', wt.LPWSTR),
                ('LastWritten', wt.FILETIME), ('CredentialBlobSize', wt.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', wt.DWORD),
                ('AttributeCount', wt.DWORD), ('Attributes', ctypes.c_void_p), ('TargetAlias', wt.LPWSTR),
                ('UserName', wt.LPWSTR)]


_advapi = ctypes.WinDLL('advapi32', use_last_error=True)
_CredRead = _advapi.CredReadW
_CredRead.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.POINTER(CREDENTIAL))]
_CredRead.restype = wt.BOOL
_CredWrite = _advapi.CredWriteW
_CredWrite.argtypes = [ctypes.POINTER(CREDENTIAL), wt.DWORD]
_CredWrite.restype = wt.BOOL
_CredDelete = _advapi.CredDeleteW
_CredDelete.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD]
_CredDelete.restype = wt.BOOL
_CredFree = _advapi.CredFree
_CredFree.argtypes = [ctypes.c_void_p]
_CredFree.restype = None


@dataclass(frozen=True)
class Stored:
    secret: str
    saved: datetime.datetime        # local time of the last write


def api_key_target(provider_id):
    return f'MWB/api-key/{provider_id}'


def read(target):
    """The stored secret and when it was saved, or None if there is none."""
    p = ctypes.POINTER(CREDENTIAL)()
    if not _CredRead(target, CRED_TYPE_GENERIC, 0, ctypes.byref(p)):
        err = ctypes.get_last_error()
        if err == ERROR_NOT_FOUND:
            return None
        raise ctypes.WinError(err)
    try:
        c = p.contents
        blob = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
        ft = (c.LastWritten.dwHighDateTime << 32) | c.LastWritten.dwLowDateTime
    finally:
        _CredFree(p)
    try:
        secret = blob.decode('utf-16-le')
    except UnicodeDecodeError:          # written by a tool that stores UTF-8
        secret = blob.decode('utf-8')
    return Stored(secret, datetime.datetime.fromtimestamp((ft - 116444736000000000) / 1e7))


def write(target, secret, user='', comment=''):
    """Create or replace the secret. UTF-16 like cmdkey and Python's keyring, so either can read it too."""
    blob = secret.encode('utf-16-le')
    buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    c = CREDENTIAL(Type=CRED_TYPE_GENERIC, TargetName=target, Comment=comment or None,
                   CredentialBlobSize=len(blob), CredentialBlob=ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)),
                   Persist=CRED_PERSIST_LOCAL_MACHINE, UserName=user or None)
    if not _CredWrite(ctypes.byref(c), 0):
        raise ctypes.WinError(ctypes.get_last_error())


def delete(target):
    """Remove the secret. Returns False if there was none."""
    if _CredDelete(target, CRED_TYPE_GENERIC, 0):
        return True
    err = ctypes.get_last_error()
    if err == ERROR_NOT_FOUND:
        return False
    raise ctypes.WinError(err)
