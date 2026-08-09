import re
import warnings
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

READ_CHUNK_BYTES = 64 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_XLSX_MEMBERS = 200
MAX_XLSX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 100
MAX_PDF_PAGES = 100
MAX_PDF_OBJECTS = 5000

IMAGE_TYPES = {
    "JPEG": {
        "mime": "image/jpeg",
        "declared": {"image/jpeg", "image/jpg", "image/pjpeg"},
        "suffixes": {".jpg", ".jpeg"},
    },
    "PNG": {
        "mime": "image/png",
        "declared": {"image/png", "image/x-png"},
        "suffixes": {".png"},
    },
    "WEBP": {
        "mime": "image/webp",
        "declared": {"image/webp"},
        "suffixes": {".webp"},
    },
}
DOCUMENT_IMAGE_FORMATS = frozenset({"JPEG", "PNG"})
PRODUCT_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
GENERIC_MIME_TYPES = {"", "application/octet-stream"}
XLSX_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "application/zip",
    "",
}
PDF_ACTIVE_MARKERS = {
    b"/javascript",
    b"/js",
    b"/launch",
    b"/openaction",
    b"/aa",
    b"/richmedia",
    b"/embeddedfile",
    b"/xfa",
    b"/submitform",
    b"/importdata",
}
PDF_NAME_BOUNDARY = rb"(?=[\x00\x09\x0a\x0c\x0d\x20()<>\[\]{}/%]|$)"
PDF_ACTIVE_KEYS = {
    "/javascript",
    "/js",
    "/launch",
    "/openaction",
    "/aa",
    "/richmedia",
    "/embeddedfile",
    "/embeddedfiles",
    "/xfa",
    "/submitform",
    "/importdata",
}

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


async def read_upload_limited(
    upload: UploadFile,
    maximum_bytes: int,
    *,
    label: str,
) -> bytes:
    """Read an upload without allowing it to grow beyond the endpoint limit."""
    content = bytearray()
    while len(content) <= maximum_bytes:
        chunk = await upload.read(
            min(READ_CHUNK_BYTES, maximum_bytes + 1 - len(content))
        )
        if not chunk:
            break
        content.extend(chunk)
    if len(content) > maximum_bytes:
        maximum_mb = maximum_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"{label}不能超过 {maximum_mb}MB",
        )
    if not content:
        raise HTTPException(status_code=422, detail=f"{label}不能为空")
    return bytes(content)


def _safe_suffix(upload: UploadFile) -> str:
    return Path(upload.filename or "").suffix.lower()


def safe_upload_path(
    base_directory: str | Path,
    storage_key: str,
    *,
    required_prefix: str,
) -> Path:
    key = PurePosixPath(storage_key)
    if (
        not storage_key
        or key.is_absolute()
        or ".." in key.parts
        or "\\" in storage_key
        or not key.parts
        or key.parts[0] != required_prefix
    ):
        raise HTTPException(status_code=500, detail="文件存储路径无效")
    base = Path(base_directory).resolve()
    candidate = (base / Path(*key.parts)).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="文件存储路径无效") from exc
    return candidate


def _check_declared_type(upload: UploadFile, actual_format: str) -> None:
    file_type = IMAGE_TYPES[actual_format]
    declared = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if declared not in GENERIC_MIME_TYPES | file_type["declared"]:
        raise HTTPException(status_code=415, detail="图片声明类型与实际内容不一致")
    suffix = _safe_suffix(upload)
    if suffix and suffix not in file_type["suffixes"]:
        raise HTTPException(status_code=415, detail="图片扩展名与实际内容不一致")


def load_verified_image(
    upload: UploadFile,
    content: bytes,
    *,
    allowed_formats: frozenset[str] = DOCUMENT_IMAGE_FORMATS,
) -> Image.Image:
    """Fully decode an explicitly allowed, single-frame image."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                actual_format = (probe.format or "").upper()
                if actual_format not in allowed_formats:
                    raise HTTPException(
                        status_code=415,
                        detail="不支持该图片格式",
                    )
                _check_declared_type(upload, actual_format)
                width, height = probe.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=415, detail="图片像素尺寸过大")
                if getattr(probe, "n_frames", 1) != 1:
                    raise HTTPException(status_code=415, detail="不支持动态或多帧图片")
                probe.verify()
            with Image.open(BytesIO(content)) as source:
                source.load()
                normalized = ImageOps.exif_transpose(source)
                return normalized.copy()
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        ValueError,
        SyntaxError,
    ) as exc:
        raise HTTPException(status_code=415, detail="图片文件无效或尺寸过大") from exc


def normalize_image(
    upload: UploadFile,
    content: bytes,
    *,
    maximum_edge: int,
    output_format: str,
    allowed_formats: frozenset[str] = DOCUMENT_IMAGE_FORMATS,
) -> tuple[bytes, str]:
    source = load_verified_image(
        upload,
        content,
        allowed_formats=allowed_formats,
    )
    try:
        source.thumbnail((maximum_edge, maximum_edge), Image.Resampling.LANCZOS)
        has_alpha = "A" in source.getbands() or "transparency" in source.info
        output = BytesIO()
        if output_format == "WEBP":
            source.convert("RGBA" if has_alpha else "RGB").save(
                output,
                format="WEBP",
                quality=86,
                method=6,
            )
            return output.getvalue(), "image/webp"
        if output_format != "DOCUMENT":
            raise ValueError("unsupported normalized image format")
        if has_alpha:
            source.convert("RGBA").save(output, format="PNG", optimize=True)
            return output.getvalue(), "image/png"
        source.convert("RGB").save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
            progressive=True,
        )
        return output.getvalue(), "image/jpeg"
    finally:
        source.close()


def _decode_pdf_name_escapes(content: bytes) -> bytes:
    return re.sub(
        rb"#([0-9a-fA-F]{2})",
        lambda match: bytes([int(match.group(1), 16)]),
        content,
    )


def _pdf_has_active_objects(root: object) -> bool:
    visited: set[tuple[int, int]] = set()
    inspected = 0

    def inspect(value: object, depth: int = 0) -> bool:
        nonlocal inspected
        if depth > 50:
            raise HTTPException(status_code=415, detail="PDF 对象嵌套过深")
        if isinstance(value, IndirectObject):
            identity = (value.idnum, value.generation)
            if identity in visited:
                return False
            visited.add(identity)
            inspected += 1
            if inspected > MAX_PDF_OBJECTS:
                raise HTTPException(status_code=415, detail="PDF 对象数量过多")
            try:
                value = value.get_object()
            except Exception as exc:
                raise HTTPException(status_code=415, detail="PDF 对象无法读取") from exc
        if isinstance(value, DictionaryObject):
            for key, child in value.items():
                key_text = str(key).lower()
                if key_text in PDF_ACTIVE_KEYS:
                    return True
                if key_text in {"/contents", "/resources"}:
                    continue
                if inspect(child, depth + 1):
                    return True
        elif isinstance(value, ArrayObject):
            return any(inspect(item, depth + 1) for item in value)
        elif isinstance(value, str) and value.lower() in PDF_ACTIVE_KEYS:
            return True
        return False

    return inspect(root)


def validate_pdf(upload: UploadFile, content: bytes) -> tuple[bytes, str]:
    declared = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if declared not in GENERIC_MIME_TYPES | {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=415, detail="PDF 声明类型与实际内容不一致")
    suffix = _safe_suffix(upload)
    if suffix and suffix != ".pdf":
        raise HTTPException(status_code=415, detail="PDF 扩展名与实际内容不一致")
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise HTTPException(status_code=415, detail="PDF 文件不完整或已损坏")
    searchable = _decode_pdf_name_escapes(content).lower()
    if re.search(re.escape(b"/encrypt") + PDF_NAME_BOUNDARY, searchable):
        raise HTTPException(status_code=415, detail="不支持加密的 PDF 文件")
    if any(
        re.search(re.escape(marker) + PDF_NAME_BOUNDARY, searchable)
        for marker in PDF_ACTIVE_MARKERS
    ):
        raise HTTPException(status_code=415, detail="PDF 包含不允许的主动内容")
    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise HTTPException(status_code=415, detail="不支持加密的 PDF 文件")
        page_count = len(reader.pages)
        if page_count < 1 or page_count > MAX_PDF_PAGES:
            raise HTTPException(status_code=415, detail="PDF 页数不符合要求")
        if _pdf_has_active_objects(reader.root_object):
            raise HTTPException(status_code=415, detail="PDF 包含不允许的主动内容")
    except HTTPException:
        raise
    except (PdfReadError, OSError, ValueError, TypeError, RecursionError) as exc:
        raise HTTPException(status_code=415, detail="PDF 文件不完整或已损坏") from exc
    return content, "application/pdf"


def validate_xlsx_upload(upload: UploadFile, content: bytes) -> None:
    declared = (upload.content_type or "").split(";", 1)[0].strip().lower()
    if declared not in XLSX_MIME_TYPES:
        raise HTTPException(status_code=415, detail="Excel 声明类型不正确")
    if _safe_suffix(upload) != ".xlsx":
        raise HTTPException(status_code=415, detail="仅支持 .xlsx 文件")
    if not content.startswith(b"PK") or not zipfile.is_zipfile(BytesIO(content)):
        raise HTTPException(status_code=415, detail="Excel 文件格式不正确")
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_XLSX_MEMBERS:
                raise HTTPException(status_code=413, detail="Excel 内部文件数量过多")
            names = {item.filename for item in members}
            if not {"[Content_Types].xml", "xl/workbook.xml"}.issubset(names):
                raise HTTPException(status_code=415, detail="Excel 文件结构不完整")
            total_uncompressed = 0
            for member in members:
                path = PurePosixPath(member.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                    raise HTTPException(status_code=415, detail="Excel 内部路径不安全")
                if member.flag_bits & 0x1:
                    raise HTTPException(status_code=415, detail="不支持加密的 Excel 文件")
                total_uncompressed += member.file_size
                if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
                    raise HTTPException(status_code=413, detail="Excel 解压后体积过大")
                if member.file_size and (
                    member.compress_size == 0
                    or member.file_size
                    > member.compress_size * MAX_XLSX_COMPRESSION_RATIO
                ):
                    raise HTTPException(status_code=413, detail="Excel 压缩比例异常")
    except HTTPException:
        raise
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise HTTPException(status_code=415, detail="Excel 文件格式不正确") from exc
