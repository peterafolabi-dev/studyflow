from django import forms

from .models import Resource

ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.txt']
MAX_UPLOAD_SIZE_MB = 20


class ResourceUploadForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ['title', 'course_code', 'resource_type', 'description', 'file']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'file': 'PDF, Word, PowerPoint or plain text — up to 20MB.',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if not file:
            return file

        ext = ('.' + file.name.rsplit('.', 1)[-1].lower()) if '.' in file.name else ''
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f'"{ext or "that file type"}" isn\'t allowed. Stick to: {", ".join(ALLOWED_EXTENSIONS)}.'
            )

        if file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f'File is too large — keep it under {MAX_UPLOAD_SIZE_MB}MB.')

        return file

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if Resource.objects.filter(title__iexact=title).exists():
            raise forms.ValidationError(
                'A resource with this exact title already exists — check it isn\'t already '
                'uploaded before adding a duplicate. (Rename it slightly if this is genuinely different.)'
            )
        return title
