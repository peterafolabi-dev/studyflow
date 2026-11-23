"""Free hosting wipes uploaded files on restart. A resource row can outlive its file, and that must not cause an error page."""
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Resource

User = get_user_model()


class MissingFileTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.tmp.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user('ada', 'ada@example.com', 'pw-12345-x')
        self.client.force_login(self.user)
        now = timezone.now()
        self.gone = Resource.objects.create(
            title='Mapping', resource_type='past_question', download_count=17, last_downloaded_at=now)
        self.gone.file.name = 'resources/2026/11/mapping.pdf'  # row says there is a file; disk says no
        self.gone.save()
        self.good = Resource.objects.create(
            title='Mathematics', resource_type='past_question', download_count=8, last_downloaded_at=now - timedelta(hours=1))
        self.good.file.save('maths.pdf', ContentFile(b'%PDF-1.4 test'))

    def test_download_of_a_wiped_file_explains_instead_of_erroring(self):
        response = self.client.get(reverse('resource_download', args=[self.gone.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('no longer on the server', ' '.join(str(m) for m in get_messages(response.wsgi_request)))
        self.gone.refresh_from_db()
        self.assertEqual(self.gone.download_count, 17)  # a failed download isn't counted

    def test_download_of_a_real_file_still_works(self):
        response = self.client.get(reverse('resource_download', args=[self.good.pk]))
        self.assertEqual(response.status_code, 200)
        self.good.refresh_from_db()
        self.assertEqual(self.good.download_count, 9)

    def test_dashboard_trending_skips_wiped_files(self):
        response = self.client.get(reverse('dashboard'))
        titles = [r.title for r in response.context['trending_resources']]
        self.assertEqual(titles, ['Mathematics'])
