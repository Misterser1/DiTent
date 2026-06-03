from pathlib import Path, PurePosixPath, PureWindowsPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


LATIN_EMAIL_ERROR = 'Введите корректный e-mail латиницей.'
RU_PHONE_ERROR = 'Введите корректный номер телефона.'


def normalize_latin_email(value):
    return str(value or '').strip().lower()


def validate_latin_email(value):
    email = normalize_latin_email(value)

    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError(LATIN_EMAIL_ERROR) from exc

    if not email or not email.isascii():
        raise ValidationError(LATIN_EMAIL_ERROR)

    return email


def normalize_ru_phone(value):
    digits = ''.join(char for char in str(value or '') if char.isdigit())

    if len(digits) == 10:
        digits = f'7{digits}'
    elif len(digits) == 11 and digits.startswith('8'):
        digits = f'7{digits[1:]}'

    return digits


def format_ru_phone(value):
    digits = normalize_ru_phone(value)

    if len(digits) != 11 or not digits.startswith('7'):
        return ''

    return f'+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}'


def validate_ru_phone(value):
    phone = format_ru_phone(value)

    if not phone:
        raise ValidationError(RU_PHONE_ERROR)

    return phone


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
