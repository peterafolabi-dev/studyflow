import os
import django
from io import BytesIO

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'studyflow.settings')
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from resources.forms import ResourceUploadForm
from studyflow.upload_config import ALLOWED_TYPES, get_allowed_types_display

print(f"Current ALLOWED_TYPES config: {ALLOWED_TYPES} (Display: {get_allowed_types_display()})")
print("=" * 60)

test_files = [
    {
        "name": "1. Real PDF",
        "filename": "sample_lecture.pdf",
        "content": b"%PDF-1.4\n1 0 obj\n<< /Title (Lecture Notes) >>\nendobj\n%%EOF",
        "content_type": "application/pdf"
    },
    {
        "name": "2. Real PNG",
        "filename": "diagram.png",
        "content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4",
        "content_type": "image/png"
    },
    {
        "name": "3. Plain Text (.txt)",
        "filename": "notes.txt",
        "content": b"These are some plain text notes for my course.",
        "content_type": "text/plain"
    },
    {
        "name": "4. Word Document (.docx)",
        "filename": "assignment.docx",
        "content": b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00Fake docx zip archive content",
        "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    },
    {
        "name": "5. Executable renamed to .pdf (.exe disguised as .pdf)",
        "filename": "malware_renamed.pdf",
        "content": b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This is a Windows executable binary disguised as a pdf",
        "content_type": "application/pdf"
    },
]

for item in test_files:
    uploaded = SimpleUploadedFile(
        item["filename"],
        item["content"],
        content_type=item["content_type"]
    )
    
    form_data = {
        'title': f"Test Resource {item['filename']}",
        'course_code': 'CSC201',
        'resource_type': 'notes',
        'description': 'Automated validation test'
    }
    
    form = ResourceUploadForm(data=form_data, files={'file': uploaded})
    is_valid = form.is_valid()
    
    print(f"Test: {item['name']} ({item['filename']})")
    print(f"Content-Type: {item['content_type']}")
    if is_valid:
        cleaned_file = form.cleaned_data['file']
        print(f"-> RESULT: [PASSED]")
        print(f"   Saved Random Filename: {cleaned_file.name}")
    else:
        file_errors = form.errors.get('file', form.errors)
        print(f"-> RESULT: [REJECTED (400)]")
        print(f"   Error Message: {list(file_errors)}")
    print("-" * 60)
