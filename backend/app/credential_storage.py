import hashlib
import hmac
import os
from uuid import uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, UploadFile

from .config import get_settings
from .upload_security import normalize_image, safe_upload_path, validate_pdf

MAX_CREDENTIAL_BYTES = 10 * 1024 * 1024
CREDENTIAL_MAGIC = b"WST2C1"
KEY_ID_BYTES = 8
NONCE_BYTES = 12


def _configured_keys() -> list[bytes]:
    settings = get_settings()
    if (
        settings.environment == "production"
        and settings.credential_encryption_key
        == "development-only-credential-key"
    ):
        raise HTTPException(status_code=503, detail="资质文件加密密钥尚未配置")
    values = [settings.credential_encryption_key]
    values.extend(
        item.strip()
        for item in settings.credential_encryption_previous_keys.split(",")
        if item.strip()
    )
    return [hashlib.sha256(value.encode()).digest() for value in values]


def _key_id(key: bytes) -> bytes:
    return hashlib.sha256(key).digest()[:KEY_ID_BYTES]


def _normalize_upload(upload: UploadFile, content: bytes) -> tuple[bytes, str]:
    if not content:
        raise HTTPException(status_code=422, detail="上传文件不能为空")
    if len(content) > MAX_CREDENTIAL_BYTES:
        raise HTTPException(status_code=413, detail="资质文件不能超过 10MB")
    if content.startswith(b"%PDF-"):
        return validate_pdf(upload, content)
    normalized, mime_type = normalize_image(
        upload,
        content,
        maximum_edge=3000,
        output_format="DOCUMENT",
    )
    if len(normalized) > MAX_CREDENTIAL_BYTES:
        raise HTTPException(status_code=413, detail="处理后的资质图片仍超过 10MB")
    return normalized, mime_type


def encrypt_upload(
    upload: UploadFile, content: bytes
) -> tuple[str, str, int, str]:
    normalized, mime_type = _normalize_upload(upload, content)
    key = _configured_keys()[0]
    key_id = _key_id(key)
    nonce = os.urandom(NONCE_BYTES)
    header = CREDENTIAL_MAGIC + key_id
    encrypted = header + nonce + AESGCM(key).encrypt(nonce, normalized, header)
    storage_key = f"credentials/{uuid4().hex}.bin"
    target = safe_upload_path(
        get_settings().upload_dir,
        storage_key,
        required_prefix="credentials",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(encrypted)
    target.chmod(0o600)
    return (
        storage_key,
        mime_type,
        len(normalized),
        hashlib.sha256(normalized).hexdigest(),
    )


def decrypt_file(storage_key: str) -> bytes:
    path = safe_upload_path(
        get_settings().upload_dir,
        storage_key,
        required_prefix="credentials",
    )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="资质文件不存在")
    encrypted = path.read_bytes()
    if len(encrypted) < NONCE_BYTES + 17:
        raise HTTPException(status_code=500, detail="资质文件已损坏")
    keys = _configured_keys()
    if encrypted.startswith(CREDENTIAL_MAGIC):
        header_size = len(CREDENTIAL_MAGIC) + KEY_ID_BYTES
        if len(encrypted) < header_size + NONCE_BYTES + 17:
            raise HTTPException(status_code=500, detail="资质文件已损坏")
        header = encrypted[:header_size]
        stored_key_id = encrypted[len(CREDENTIAL_MAGIC):header_size]
        nonce = encrypted[header_size:header_size + NONCE_BYTES]
        ciphertext = encrypted[header_size + NONCE_BYTES:]
        matching_key = next(
            (key for key in keys if hmac.compare_digest(_key_id(key), stored_key_id)),
            None,
        )
        if matching_key is None:
            raise HTTPException(status_code=500, detail="资质文件加密密钥版本不可用")
        try:
            return AESGCM(matching_key).decrypt(nonce, ciphertext, header)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="资质文件无法解密") from exc

    # Compatibility with credential files created before the versioned header
    # was introduced. Previous keys allow a staged key rotation.
    nonce, ciphertext = encrypted[:NONCE_BYTES], encrypted[NONCE_BYTES:]
    for key in keys:
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception:
            continue
    raise HTTPException(status_code=500, detail="资质文件无法解密")


def delete_encrypted_file(storage_key: str) -> None:
    safe_upload_path(
        get_settings().upload_dir,
        storage_key,
        required_prefix="credentials",
    ).unlink(missing_ok=True)
