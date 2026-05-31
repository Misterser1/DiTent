from pathlib import Path, PurePosixPath, PureWindowsPath

from django.conf import settings
from django.core.exceptions import ValidationError


SIGNATURES = {
    '.gif': (b'GIF87a', b'GIF89a'),
    '.jpg': (b'\xff\xd8\xff',),
    '.jpeg': (b'\xff\xd8\xff',),
    '.pdf': (b'%PDF-',),
    '.png': (b'\x89PNG\r\n\x1a\n',),
    '.zip': (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'),
}


def has_valid_signature(file, suffix):
    if suffix == '.webp':
        header = file.read(12)
        file.seek(0)
        return header.startswith(b'RIFF') and header[8:12] == b'WEBP'

    if suffix in {'.heic', '.heif'}:
        header = file.read(32)
        file.seek(0)
        return (
            b'ftypheic' in header
            or b'ftypheix' in header
            or b'ftyphevc' in header
            or b'ftyphevx' in header
            or b'ftypmif1' in header
        )

    signatures = SIGNATURES.get(suffix)
    if not signatures:
        return True

    max_length = max(len(signature) for signature in signatures)
    header = file.read(max_length)
    file.seek(0)
    return any(header.startswith(signature) for signature in signatures)


def validate_uploaded_file(file):
    original_name = str(file.name or '').strip()
    normalized_name = original_name.replace('\\', '/')
    file_name = PurePosixPath(normalized_name).name or PureWindowsPath(original_name).name

    if not file_name or file_name in {'.', '..'} or '..' in PurePosixPath(normalized_name).parts:
        raise ValidationError('Некорректное имя файла.')

    file.name = file_name
    suffix = Path(file.name).suffix.lower()

    if suffix not in settings.DITENT_ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(f'Расширение файла "{file.name}" не разрешено.')

    if file.size > settings.DITENT_MAX_UPLOAD_SIZE:
        max_mb = settings.DITENT_MAX_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(f'Файл "{file.name}" больше допустимого размера {max_mb} МБ.')

    content_type = getattr(file, 'content_type', '') or ''
    if content_type and content_type not in settings.DITENT_ALLOWED_UPLOAD_TYPES:
        raise ValidationError(f'Тип файла "{file.name}" не разрешен.')

    if not has_valid_signature(file, suffix):
        raise ValidationError(f'Содержимое файла "{file.name}" не соответствует его расширению.')

    if '..' in Path(file.name).parts or Path(file.name).name != file.name:
        raise ValidationError('Некорректное имя файла.')

    return file


def validate_uploaded_files(files):
    if len(files) > settings.DITENT_MAX_UPLOAD_COUNT:
        raise ValidationError(f'Можно загрузить не больше {settings.DITENT_MAX_UPLOAD_COUNT} файлов.')

    for file in files:
        validate_uploaded_file(file)
