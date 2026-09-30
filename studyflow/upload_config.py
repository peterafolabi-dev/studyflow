import os

# Definition of supported file types, their extensions, MIME types, and magic bytes
TYPE_DEFINITIONS = {
    'PDF': {
        'extensions': ['.pdf'],
        'mime_types': ['application/pdf'],
        'magic_bytes': [b'%PDF-'],
    },
    'PNG': {
        'extensions': ['.png'],
        'mime_types': ['image/png'],
        'magic_bytes': [b'\x89PNG\r\n\x1a\n'],
    },
    'JPG': {
        'extensions': ['.jpg', '.jpeg'],
        'mime_types': ['image/jpeg'],
        'magic_bytes': [b'\xff\xd8'],
    },
    'JPEG': {
        'extensions': ['.jpg', '.jpeg'],
        'mime_types': ['image/jpeg'],
        'magic_bytes': [b'\xff\xd8'],
    },
}

# ALLOWED_TYPES configuration
# Default: PDF only. Can be overridden in .env: e.g. ALLOWED_TYPES=PDF, PNG, JPG, JPEG
_raw_allowed = os.environ.get('ALLOWED_TYPES', 'PDF')
ALLOWED_TYPES = [t.strip().upper() for t in _raw_allowed.split(',') if t.strip()]

MAX_UPLOAD_SIZE_MB = int(os.environ.get('MAX_UPLOAD_SIZE_MB', 10))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def get_allowed_extensions():
    exts = set()
    for t in ALLOWED_TYPES:
        if t in TYPE_DEFINITIONS:
            exts.update(TYPE_DEFINITIONS[t]['extensions'])
    return sorted(list(exts))


def get_allowed_mime_types():
    mimes = set()
    for t in ALLOWED_TYPES:
        if t in TYPE_DEFINITIONS:
            mimes.update(TYPE_DEFINITIONS[t]['mime_types'])
    return sorted(list(mimes))


def get_accept_attribute():
    parts = get_allowed_extensions() + get_allowed_mime_types()
    return ','.join(parts)


def get_allowed_types_display():
    unique = []
    for t in ALLOWED_TYPES:
        name = 'JPG/JPEG' if t in ('JPG', 'JPEG') else t
        if name not in unique:
            unique.append(name)
    return ', '.join(unique)


def validate_magic_bytes(file_obj, ext):
    ext = ext.lower()
    pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0
    header = file_obj.read(16)
    if hasattr(file_obj, 'seek'):
        file_obj.seek(pos)

    for t in ALLOWED_TYPES:
        if t in TYPE_DEFINITIONS:
            config = TYPE_DEFINITIONS[t]
            if ext in config['extensions']:
                for magic in config['magic_bytes']:
                    if header.startswith(magic):
                        return True
    return False
