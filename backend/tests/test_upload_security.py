import asyncio
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from openpyxl import Workbook
from PIL import Image
from pypdf import PdfWriter
from starlette.datastructures import Headers

from app import upload_security
from app import credential_storage
from app.upload_security import (
    PRODUCT_IMAGE_FORMATS,
    normalize_image,
    read_upload_limited,
    safe_upload_path,
    validate_pdf,
    validate_xlsx_upload,
)


def upload(
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        size=len(content),
        headers=Headers({"content-type": content_type}),
    )


def image_bytes(image_format: str = "PNG") -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), "#16877e").save(output, format=image_format)
    return output.getvalue()


def xlsx_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["日期", "访客", "订单", "营业额", "评分", "到店", "外卖", "团购", "其他", "高峰小时"])
    sheet.append(["2026-08-01", 10, 4, 100, 4.8, 2, 1, 1, 0, 12])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def pdf_bytes(*, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    if encrypted:
        writer.encrypt("test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def assert_http_error(status_code: int, function, *args, **kwargs) -> HTTPException:
    with pytest.raises(HTTPException) as captured:
        function(*args, **kwargs)
    assert captured.value.status_code == status_code
    return captured.value


def test_limited_reader_rejects_oversized_and_empty_uploads():
    too_large = upload("large.png", b"x" * 1025, "image/png")
    with pytest.raises(HTTPException) as captured:
        asyncio.run(read_upload_limited(too_large, 1024, label="测试文件"))
    assert captured.value.status_code == 413

    empty = upload("empty.png", b"", "image/png")
    with pytest.raises(HTTPException) as captured:
        asyncio.run(read_upload_limited(empty, 1024, label="测试文件"))
    assert captured.value.status_code == 422


def test_image_validation_only_accepts_explicit_real_formats():
    png = image_bytes("PNG")
    normalized, mime_type = normalize_image(
        upload("product.png", png, "image/png"),
        png,
        maximum_edge=2000,
        output_format="WEBP",
    )
    assert normalized.startswith(b"RIFF")
    assert mime_type == "image/webp"

    webp = image_bytes("WEBP")
    normalized, mime_type = normalize_image(
        upload("product.webp", webp, "image/webp"),
        webp,
        maximum_edge=2000,
        output_format="WEBP",
        allowed_formats=PRODUCT_IMAGE_FORMATS,
    )
    assert normalized.startswith(b"RIFF")
    assert mime_type == "image/webp"

    gif = image_bytes("GIF")
    assert_http_error(
        415,
        normalize_image,
        upload("fake.png", gif, "image/png"),
        gif,
        maximum_edge=2000,
        output_format="WEBP",
    )
    assert_http_error(
        415,
        normalize_image,
        upload("fake.jpg", png, "image/jpeg"),
        png,
        maximum_edge=2000,
        output_format="WEBP",
    )


def test_image_validation_enforces_pixel_limit(monkeypatch):
    png = image_bytes("PNG")
    monkeypatch.setattr(upload_security, "MAX_IMAGE_PIXELS", 100)
    assert_http_error(
        415,
        normalize_image,
        upload("large-pixels.png", png, "image/png"),
        png,
        maximum_edge=2000,
        output_format="WEBP",
    )


def test_pdf_validation_rejects_active_encrypted_and_disguised_files():
    safe_pdf = pdf_bytes()
    content, mime_type = validate_pdf(
        upload("license.pdf", safe_pdf, "application/pdf"),
        safe_pdf,
    )
    assert content == safe_pdf
    assert mime_type == "application/pdf"

    for marker in (b"/OpenAction", b"/Java#53cript", b"/EmbeddedFile"):
        unsafe = b"%PDF-1.4\n" + marker + b"\n%%EOF\n"
        assert_http_error(
            415,
            validate_pdf,
            upload("unsafe.pdf", unsafe, "application/pdf"),
            unsafe,
        )
    encrypted = pdf_bytes(encrypted=True)
    assert_http_error(
        415,
        validate_pdf,
        upload("encrypted.pdf", encrypted, "application/pdf"),
        encrypted,
    )
    assert_http_error(
        415,
        validate_pdf,
        upload("license.png", safe_pdf, "application/pdf"),
        safe_pdf,
    )


def test_xlsx_validation_accepts_template_and_rejects_zip_bomb():
    valid = xlsx_bytes()
    validate_xlsx_upload(
        upload(
            "data.xlsx",
            valid,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        valid,
    )

    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", "<workbook />")
        archive.writestr("xl/sharedStrings.xml", "A" * (1024 * 1024))
    bomb = output.getvalue()
    assert_http_error(
        413,
        validate_xlsx_upload,
        upload("bomb.xlsx", bomb, "application/octet-stream"),
        bomb,
    )


def test_xlsx_validation_rejects_wrong_type_and_unsafe_paths():
    valid = xlsx_bytes()
    assert_http_error(
        415,
        validate_xlsx_upload,
        upload("data.zip", valid, "application/zip"),
        valid,
    )

    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("xl/workbook.xml", "<workbook />")
        archive.writestr("../outside.xml", "unsafe")
    unsafe = output.getvalue()
    assert_http_error(
        415,
        validate_xlsx_upload,
        upload("unsafe.xlsx", unsafe),
        unsafe,
    )


def test_storage_paths_cannot_escape_upload_directory(tmp_path):
    safe = safe_upload_path(
        tmp_path,
        "products/example.webp",
        required_prefix="products",
    )
    assert safe == tmp_path / "products" / "example.webp"
    for storage_key in (
        "../outside.bin",
        "products/../../outside.bin",
        "/tmp/outside.bin",
        "products\\..\\outside.bin",
        "credentials/wrong-prefix.bin",
    ):
        assert_http_error(
            500,
            safe_upload_path,
            tmp_path,
            storage_key,
            required_prefix="products",
        )


def test_credential_encryption_supports_safe_key_rotation(tmp_path, monkeypatch):
    old_key = "old-credential-key-for-isolated-tests-0123456789"
    new_key = "new-credential-key-for-isolated-tests-0123456789"

    def settings(current_key: str, previous_keys: str = ""):
        return SimpleNamespace(
            environment="testing",
            upload_dir=str(tmp_path),
            credential_encryption_key=current_key,
            credential_encryption_previous_keys=previous_keys,
        )

    monkeypatch.setattr(
        credential_storage,
        "get_settings",
        lambda: settings(old_key),
    )
    original = image_bytes("PNG")
    storage_key, _, _, _ = credential_storage.encrypt_upload(
        upload("license.png", original, "image/png"),
        original,
    )
    encrypted = (tmp_path / storage_key).read_bytes()
    assert encrypted.startswith(credential_storage.CREDENTIAL_MAGIC)

    monkeypatch.setattr(
        credential_storage,
        "get_settings",
        lambda: settings(new_key, old_key),
    )
    decrypted = credential_storage.decrypt_file(storage_key)
    assert decrypted.startswith((b"\x89PNG", b"\xff\xd8\xff"))

    monkeypatch.setattr(
        credential_storage,
        "get_settings",
        lambda: settings(new_key),
    )
    assert_http_error(500, credential_storage.decrypt_file, storage_key)
