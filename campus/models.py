from django.conf import settings
from django.db import models
from django.utils import timezone


class StudySpot(models.Model):
    CAMPUS_CHOICES = [
        ('Gidan Kwano', 'Main Campus (Gidan Kwano)'),
        ('Bosso', 'Bosso Campus'),
    ]

    POWER_STATUS_CHOICES = [
        ('gen_on', 'Generator Running ⚡'),
        ('grid_on', 'NEPA / Public Grid On 💡'),
        ('no_power', 'Outage / No Light 🌑'),
    ]

    name = models.CharField(max_length=150)
    campus = models.CharField(max_length=30, choices=CAMPUS_CHOICES, default='Gidan Kwano')
    location_desc = models.CharField(max_length=200, help_text="e.g. Near School of Agriculture or Behind ETF Hall")
    capacity_estimate = models.CharField(max_length=50, blank=True, default="150+ seats")
    has_wifi = models.BooleanField(default=False)
    has_sockets = models.BooleanField(default=True)
    has_ac = models.BooleanField(default=False)
    current_status = models.CharField(max_length=20, choices=POWER_STATUS_CHOICES, default='gen_on')
    last_reported_at = models.DateTimeField(default=timezone.now)
    last_reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='spot_reports'
    )

    class Meta:
        ordering = ['campus', 'name']

    def __str__(self):
        return f"{self.name} ({self.campus}) - {self.get_current_status_display()}"


class PowerVote(models.Model):
    spot = models.ForeignKey(StudySpot, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=StudySpot.POWER_STATUS_CHOICES)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-voted_at']


class CourseNotice(models.Model):
    URGENCY_CHOICES = [
        ('normal', 'General Notice'),
        ('venue_change', 'Venue / Time Shift 📍'),
        ('urgent', 'Urgent Announcement ⚠️'),
        ('exam_alert', 'Exam / Test Alert 📝'),
    ]

    LEVEL_CHOICES = [
        (100, '100 Level'),
        (200, '200 Level'),
        (300, '300 Level'),
        (400, '400 Level'),
        (500, '500 Level'),
        (0, 'All Levels'),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField()
    course_code = models.CharField(max_length=20, blank=True, help_text="e.g. CSC 301 or MAT 111")
    department = models.CharField(max_length=100, blank=True, default="All Departments")
    level = models.PositiveSmallIntegerField(choices=LEVEL_CHOICES, default=0)
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='normal')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notices')
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"[{self.course_code or 'Campus'}] {self.title}"


class LodgeReview(models.Model):
    AREA_CHOICES = [
        ('GK Gate', 'Gidan Kwano Gate Area'),
        ('Bosso', 'Bosso / Low-Cost'),
        ('F-Layout', 'F-Layout / Mobil'),
        ('Barkin Sale', 'Barkin Sale'),
        ('Tunga', 'Tunga / Minna Town'),
        ('Other', 'Other Lodge Area'),
    ]

    lodge_name = models.CharField(max_length=150)
    area = models.CharField(max_length=40, choices=AREA_CHOICES, default='GK Gate')
    rent_estimate = models.CharField(max_length=60, help_text="e.g. ₦120,000 - ₦180,000 / year")
    water_rating = models.PositiveSmallIntegerField(default=4, help_text="1 to 5 stars")
    power_rating = models.PositiveSmallIntegerField(default=3, help_text="1 to 5 stars")
    security_rating = models.PositiveSmallIntegerField(default=4, help_text="1 to 5 stars")
    landlord_rating = models.PositiveSmallIntegerField(default=4, help_text="1 to 5 stars")
    review_text = models.TextField()
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lodge_reviews')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.lodge_name} ({self.area})"

    @property
    def average_rating(self):
        return round((self.water_rating + self.power_rating + self.security_rating + self.landlord_rating) / 4, 1)


class RoommateProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='roommate_profile')
    department = models.CharField(max_length=100)
    level = models.PositiveSmallIntegerField(default=200)
    budget_range = models.CharField(max_length=60, help_text="e.g. ₦60k - ₦90k share")
    preferred_area = models.CharField(max_length=60, default="GK Gate")
    cleanliness = models.CharField(max_length=40, default="Very Neat")
    sleep_habit = models.CharField(max_length=40, default="Night Owl (Studies late)")
    study_habit = models.CharField(max_length=40, default="Quiet / Serious")
    bio = models.TextField(max_length=300, blank=True)
    whatsapp_number = models.CharField(max_length=25, help_text="e.g. 08012345678")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ({self.department} {self.level}L)"


class SIWESCompany(models.Model):
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=60, default="Abuja")
    state = models.CharField(max_length=60, default="FCT")
    industry = models.CharField(max_length=80, help_text="e.g. Software, Telecomm, Civil Engineering, Oil & Gas")
    takes_it_students = models.BooleanField(default=True)
    stipend_info = models.CharField(max_length=80, default="Paid / Unpaid depends on department")
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True, help_text="Application tips or accepted faculties")

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'SIWES Companies'

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} ({self.industry})"


class SIWESLogEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='siwes_logs')
    week_number = models.PositiveSmallIntegerField(default=1)
    date = models.DateField(default=timezone.localdate)
    department_unit = models.CharField(max_length=100, help_text="e.g. Network Operations Center or Quality Control")
    work_done = models.TextField(help_text="Detailed description of technical tasks completed today")
    skills_acquired = models.CharField(max_length=250, help_text="e.g. Fiber splicing, Django API testing, Soil compaction")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-week_number']

    def __str__(self):
        return f"{self.user.username} - Week {self.week_number} ({self.date})"


class MarketplaceItem(models.Model):
    CATEGORY_CHOICES = [
        ('textbook', 'Textbook / Course Material 📚'),
        ('drawing_board', 'Engineering Drawing Board / T-Square 📐'),
        ('lab_coat', 'Lab Coat / Dissection Kit 🥼'),
        ('calculator', 'Scientific / Graphing Calculator 🧮'),
        ('gadget', 'Hostel Gadget / Fan / Lamp ⚡'),
        ('other', 'Other Campus Item 📦'),
    ]

    CONDITION_CHOICES = [
        ('new', 'Brand New'),
        ('like_new', 'Like New'),
        ('good', 'Good Condition'),
        ('fair', 'Fair / Readable'),
    ]

    title = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='textbook')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_free = models.BooleanField(default=False, help_text="Check if giving away for free to a junior student")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    description = models.TextField(blank=True)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='marketplace_items')
    whatsapp_number = models.CharField(max_length=25, help_text="WhatsApp number with country code, e.g. 2348012345678")
    is_sold = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - ₦{self.price} ({self.get_category_display()})"


class EmergencyContact(models.Model):
    CATEGORY_CHOICES = [
        ('clinic', 'University Clinic & Medical Ambulance 🚑'),
        ('security', 'Campus Security Post & Gate Patrol 🛡️'),
        ('sug', 'Student Union (SUG) Welfare Team 🎓'),
        ('fire', 'Fire & Emergency Safety Service 🚒'),
        ('counseling', 'Student Mental Health & Counseling Unit 🧠'),
    ]

    title = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    phone_number = models.CharField(max_length=40)
    campus = models.CharField(max_length=50, default="Both Campuses")
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['category', 'title']

    def __str__(self):
        return f"{self.title}: {self.phone_number}"

