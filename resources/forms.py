import uuid
from django import forms
from .models import Resource
from studyflow.upload_config import (
    get_allowed_extensions,
    get_allowed_mime_types,
    get_accept_attribute,
    get_allowed_types_display,
    validate_magic_bytes,
    MAX_UPLOAD_SIZE_MB,
    MAX_UPLOAD_SIZE_BYTES,
)


class ResourceUploadForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['title', 'course_code', 'resource_type', 'description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'file': forms.FileInput(attrs={'accept': get_accept_attribute()}),
        }
        help_texts = {
            'file': f'Allowed: {get_allowed_types_display()} — up to {MAX_UPLOAD_SIZE_MB}MB.',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            return file

        # Check file size limit
        if file.size > MAX_UPLOAD_SIZE_BYTES:
            raise forms.ValidationError(f'File is too large — keep it under {MAX_UPLOAD_SIZE_MB}MB.')

        # Check extension
        ext = ('.' + file.name.rsplit('.', 1)[-1].lower()) if '.' in file.name else ''
        allowed_extensions = get_allowed_extensions()
        if ext not in allowed_extensions:
            raise forms.ValidationError(f'Only {get_allowed_types_display()} files are allowed.')

        # Check MIME type
        content_type = getattr(file, 'content_type', '')
        allowed_mimes = get_allowed_mime_types()
        if content_type and content_type.lower() not in allowed_mimes:
            raise forms.ValidationError(f'Only {get_allowed_types_display()} files are allowed.')

        # Check magic bytes for genuine file content
        if not validate_magic_bytes(file, ext):
            raise forms.ValidationError(f'Invalid file content: The file does not match a valid {get_allowed_types_display()} signature.')

        # Generate a safe random filename so original filename is never the storage path
        file.name = f"{uuid.uuid4().hex}{ext}"

        return file

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if Resource.objects.filter(title__iexact=title).exists():
            raise forms.ValidationError(
                'A resource with this exact title already exists — check it isn\'t already '
                'uploaded before adding a duplicate. (Rename it slightly if this is genuinely different.)'
            )
        return title
