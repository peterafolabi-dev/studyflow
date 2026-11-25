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


class CloudStorageReadinessTests(MissingFileTests):
    """Reading files must not depend on a local path, so it also works once uploads live on Cloudinary."""

    def test_open_for_reading_returns_the_bytes_without_using_a_path(self):
        data = self.good.open_for_reading().read()
        self.assertEqual(data, b'%PDF-1.4 test')

    def test_with_cloud_storage_the_real_check_is_used_and_cached(self):
        from unittest import mock
        from django.core.cache import cache
        cache.clear()
        with override_settings(USING_CLOUD_STORAGE=True), \
             mock.patch('django.core.files.storage.FileSystemStorage.exists', return_value=False) as ex:
            self.assertFalse(self.gone.file_available())
            self.assertFalse(self.gone.file_available())
            self.assertEqual(ex.call_count, 1)            # second call served from cache
            self.assertFalse(Resource(title='no file').file_available())


class CloudMissingFileTests(TestCase):
    """With cloud storage on, file_available() is optimistic; opening a lost file must not 500."""

    def test_download_when_storage_cannot_open_file(self):
        from unittest import mock
        from django.contrib.auth import get_user_model
        from django.core.files.base import ContentFile
        from .models import Resource
        user = get_user_model().objects.create_user('cloudu', 'c@example.com', 'pw12345!x')
        res = Resource(title='Mapping', resource_type='past_question', uploaded_by=user)
        res.file.save('gone.pdf', ContentFile(b'x'), save=True)
        self.client.force_login(user)
        with mock.patch.object(Resource, 'file_available', return_value=True), \
             mock.patch('django.db.models.fields.files.FieldFile.open', side_effect=RuntimeError('404 from cloud')):
            r = self.client.get(f'/resources/{res.pk}/download/', follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'missing from storage')


class AdminCleanupTests(TestCase):
    def test_admin_action_deletes_only_entries_with_missing_files(self):
        from unittest import mock
        from .admin import ResourceAdmin
        from django.contrib import admin as dj_admin
        from django.test import RequestFactory
        user = get_user_model().objects.create_superuser('boss', 'b@example.com', 'pw12345!x')
        gone = Resource.objects.create(title='Gone', resource_type='notes', uploaded_by=user, file='resources/x/gone.pdf')
        keep = Resource.objects.create(title='Keep', resource_type='notes', uploaded_by=user, file='resources/x/keep.pdf')
        ma = ResourceAdmin(Resource, dj_admin.site)
        req = RequestFactory().post('/'); req.user = user
        req.session = {}; req._messages = mock.MagicMock()
        with mock.patch.object(Resource, 'file_available', lambda self: self.pk == keep.pk):
            ma.delete_missing_files(req, Resource.objects.all())
        self.assertFalse(Resource.objects.filter(pk=gone.pk).exists())
        self.assertTrue(Resource.objects.filter(pk=keep.pk).exists())


class AIMissingFileTests(TestCase):
    def test_ai_endpoints_return_friendly_error_for_lost_file(self):
        user = get_user_model().objects.create_user('aiu', 'a@example.com', 'pw12345!x')
        res = Resource.objects.create(title='Lost', resource_type='notes', uploaded_by=user, file='resources/x/lost.pdf')
        self.client.force_login(user)
        for name in ('resource_ai_summarize', 'resource_ai_quiz', 'resource_ai_flashcards', 'resource_ai_generate_cbt'):
            try:
                url = reverse(name, args=[res.pk])
            except Exception:
                continue
            r = self.client.post(url)
            self.assertEqual(r.status_code, 410, name)
            self.assertIn('missing from storage', r.json()['error'])


class StorageSelectionTests(TestCase):
    """The storage backend is chosen from environment variables at startup."""

    def _backend(self, env):
        import os, subprocess, sys
        full = {k: v for k, v in os.environ.items() if not k.startswith(('S3_', 'CLOUDINARY'))}
        full.update(env)
        code = ("import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','studyflow.settings');django.setup();"
                "from django.core.files.storage import storages;d=storages['default'];print(type(d).__module__+'.'+type(d).__name__)")
        return subprocess.run([sys.executable, '-c', code], env=full, capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]

    S3 = {'S3_BUCKET_NAME': 'b', 'S3_ACCESS_KEY_ID': 'k', 'S3_SECRET_ACCESS_KEY': 's', 'S3_ENDPOINT_URL': 'https://example.supabase.co/storage/v1/s3'}

    def test_s3_env_selects_s3_storage(self):
        self.assertTrue(self._backend(self.S3).endswith('S3Storage'))

    def test_s3_wins_over_cloudinary_and_default_is_local_disk(self):
        self.assertTrue(self._backend({**self.S3, 'CLOUDINARY_URL': 'cloudinary://a:b@c'}).endswith('S3Storage'))
        self.assertTrue(self._backend({}).endswith('FileSystemStorage'))

    def test_incomplete_s3_settings_fall_back(self):
        self.assertTrue(self._backend({'S3_BUCKET_NAME': 'b'}).endswith('FileSystemStorage'))
