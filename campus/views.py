from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import (
    StudySpot, PowerVote, CourseNotice, LodgeReview, RoommateProfile,
    SIWESCompany, SIWESLogEntry, MarketplaceItem, EmergencyContact
)


def campus_hub(request):
    """Main overview hub for Campus Life & Student Welfare."""
    spots = StudySpot.objects.all()[:6]
    notices = CourseNotice.objects.all()[:5]
    recent_lodges = LodgeReview.objects.all()[:3]
    recent_market = MarketplaceItem.objects.filter(is_sold=False)[:4]
    emergencies = EmergencyContact.objects.all()[:4]

    # Seed initial demo spots if empty
    if not spots.exists():
        _seed_initial_campus_data()
        spots = StudySpot.objects.all()[:6]
        emergencies = EmergencyContact.objects.all()[:4]

    context = {
        'spots': spots,
        'notices': notices,
        'recent_lodges': recent_lodges,
        'recent_market': recent_market,
        'emergencies': emergencies,
    }
    return render(request, 'campus/campus_hub.html', context)


def power_tracker(request):
    """'Where is Light?' Live campus study spot power and generator tracker."""
    campus_filter = request.GET.get('campus', '')
    spots = StudySpot.objects.all()
    if campus_filter:
        spots = spots.filter(campus=campus_filter)

    if not spots.exists():
        _seed_initial_campus_data()
        spots = StudySpot.objects.all()

    context = {
        'spots': spots,
        'selected_campus': campus_filter,
    }
    return render(request, 'campus/power_tracker.html', context)


@login_required
def report_power_status(request, spot_id):
    """Submits a real-time status update for a campus study spot."""
    spot = get_object_or_404(StudySpot, id=spot_id)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(StudySpot.POWER_STATUS_CHOICES):
            spot.current_status = new_status
            spot.last_reported_at = timezone.now()
            spot.last_reported_by = request.user
            spot.save()

            PowerVote.objects.create(
                spot=spot,
                user=request.user,
                status=new_status
            )
            messages.success(request, f"Thanks for reporting! {spot.name} status updated to {spot.get_current_status_display()}. ⚡")
    return redirect('power_tracker')


def notice_board(request):
    """Official Course Rep & Departmental Notice Board."""
    level = request.GET.get('level', '')
    urgency = request.GET.get('urgency', '')
    search = request.GET.get('q', '').strip()

    notices = CourseNotice.objects.all()
    if level and level.isdigit():
        notices = notices.filter(level=int(level))
    if urgency:
        notices = notices.filter(urgency=urgency)
    if search:
        notices = notices.filter(models.Q(title__icontains=search) | models.Q(course_code__icontains=search) | models.Q(department__icontains=search))

    context = {
        'notices': notices,
        'selected_level': level,
        'selected_urgency': urgency,
        'search_query': search,
    }
    return render(request, 'campus/notices.html', context)


@login_required
def create_notice(request):
    """Course Reps and students can post official notices."""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        course_code = request.POST.get('course_code', '').strip().upper()
        department = request.POST.get('department', '').strip() or 'All Departments'
        level = int(request.POST.get('level', 0))
        urgency = request.POST.get('urgency', 'normal')

        if title and body:
            CourseNotice.objects.create(
                title=title,
                body=body,
                course_code=course_code,
                department=department,
                level=level,
                urgency=urgency,
                author=request.user,
            )
            messages.success(request, "Notice broadcasted successfully to your department/level! 📢")
            return redirect('notice_board')
        else:
            messages.error(request, "Please enter both a title and message body.")
    return redirect('notice_board')


def lodge_and_roommate_hub(request):
    """Off-Campus Lodge Reviews & Roommate Matcher."""
    area = request.GET.get('area', '')
    lodges = LodgeReview.objects.all()
    if area:
        lodges = lodges.filter(area=area)

    roommates = RoommateProfile.objects.filter(is_active=True).select_related('user')
    user_roommate_profile = None
    if request.user.is_authenticated:
        user_roommate_profile = RoommateProfile.objects.filter(user=request.user).first()

    context = {
        'lodges': lodges,
        'roommates': roommates,
        'selected_area': area,
        'user_roommate_profile': user_roommate_profile,
    }
    return render(request, 'campus/lodge_roommate.html', context)


@login_required
def add_lodge_review(request):
    if request.method == 'POST':
        lodge_name = request.POST.get('lodge_name', '').strip()
        area = request.POST.get('area', 'GK Gate')
        rent_estimate = request.POST.get('rent_estimate', '').strip()
        water = int(request.POST.get('water_rating', 4))
        power = int(request.POST.get('power_rating', 3))
        security = int(request.POST.get('security_rating', 4))
        landlord = int(request.POST.get('landlord_rating', 4))
        review_text = request.POST.get('review_text', '').strip()

        if lodge_name and review_text:
            LodgeReview.objects.create(
                lodge_name=lodge_name,
                area=area,
                rent_estimate=rent_estimate,
                water_rating=water,
                power_rating=power,
                security_rating=security,
                landlord_rating=landlord,
                review_text=review_text,
                reviewer=request.user,
            )
            messages.success(request, f"Review for {lodge_name} added to the lodge directory! 🏠")
    return redirect('lodge_roommate_hub')


@login_required
def update_roommate_profile(request):
    if request.method == 'POST':
        department = request.POST.get('department', '').strip()
        level = int(request.POST.get('level', 200))
        budget = request.POST.get('budget_range', '').strip()
        preferred_area = request.POST.get('preferred_area', 'GK Gate')
        cleanliness = request.POST.get('cleanliness', 'Very Neat')
        sleep_habit = request.POST.get('sleep_habit', 'Night Owl')
        study_habit = request.POST.get('study_habit', 'Quiet / Serious')
        whatsapp = request.POST.get('whatsapp_number', '').strip()
        bio = request.POST.get('bio', '').strip()

        RoommateProfile.objects.update_or_create(
            user=request.user,
            defaults={
                'department': department,
                'level': level,
                'budget_range': budget,
                'preferred_area': preferred_area,
                'cleanliness': cleanliness,
                'sleep_habit': sleep_habit,
                'study_habit': study_habit,
                'whatsapp_number': whatsapp,
                'bio': bio,
                'is_active': True,
            }
        )
        messages.success(request, "Your roommate search profile has been updated! 🤝")
    return redirect('lodge_roommate_hub')


def siwes_hub(request):
    """SIWES / IT Placement Directory & Daily Logbook Assistant."""
    industry = request.GET.get('industry', '')
    state = request.GET.get('state', '')
    companies = SIWESCompany.objects.all()

    if industry:
        companies = companies.filter(industry__icontains=industry)
    if state:
        companies = companies.filter(state__icontains=state)

    if not companies.exists():
        _seed_siwes_companies()
        companies = SIWESCompany.objects.all()

    user_logs = []
    if request.user.is_authenticated:
        user_logs = SIWESLogEntry.objects.filter(user=request.user)[:10]

    context = {
        'companies': companies,
        'user_logs': user_logs,
        'selected_industry': industry,
        'selected_state': state,
    }
    return render(request, 'campus/siwes_hub.html', context)


@login_required
def add_siwes_log(request):
    if request.method == 'POST':
        week = int(request.POST.get('week_number', 1))
        unit = request.POST.get('department_unit', '').strip()
        work = request.POST.get('work_done', '').strip()
        skills = request.POST.get('skills_acquired', '').strip()

        if work:
            SIWESLogEntry.objects.create(
                user=request.user,
                week_number=week,
                department_unit=unit,
                work_done=work,
                skills_acquired=skills,
            )
            messages.success(request, f"Week {week} log entry saved to your SIWES journal! 💼")
    return redirect('siwes_hub')


def marketplace(request):
    """Campus Marketplace (Textbooks, Drawing Boards, Lab Coats, Calculators)."""
    cat = request.GET.get('category', '')
    items = MarketplaceItem.objects.filter(is_sold=False)
    if cat:
        items = items.filter(category=cat)

    context = {
        'items': items,
        'selected_category': cat,
    }
    return render(request, 'campus/marketplace.html', context)


@login_required
def create_listing(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        category = request.POST.get('category', 'textbook')
        price_val = request.POST.get('price', '0')
        is_free = request.POST.get('is_free') == 'on'
        condition = request.POST.get('condition', 'good')
        description = request.POST.get('description', '').strip()
        whatsapp = request.POST.get('whatsapp_number', '').strip()

        try:
            price = float(price_val) if not is_free else 0.0
        except ValueError:
            price = 0.0

        if title and whatsapp:
            MarketplaceItem.objects.create(
                title=title,
                category=category,
                price=price,
                is_free=is_free,
                condition=condition,
                description=description,
                seller=request.user,
                whatsapp_number=whatsapp,
            )
            messages.success(request, f"Your listing for '{title}' is live on the Campus Marketplace! 🛍️")
            return redirect('marketplace')
        else:
            messages.error(request, "Please enter an item title and valid WhatsApp number.")
    return redirect('marketplace')


def emergency_directory(request):
    """Campus Emergency & Quick-Dial Helpline Directory."""
    emergencies = EmergencyContact.objects.all()
    if not emergencies.exists():
        _seed_initial_campus_data()
        emergencies = EmergencyContact.objects.all()

    return render(request, 'campus/emergency.html', {'emergencies': emergencies})


def _seed_initial_campus_data():
    """Initializes realistic FUT Minna campus study spots and emergency contacts."""
    initial_spots = [
        ("IBB Central Library", "Gidan Kwano", "Main campus library, ground & 1st floors", "500+ seats", True, True, True, "gen_on"),
        ("SEET Complex Study Hall", "Gidan Kwano", "School of Engineering & Engineering Tech", "250+ seats", False, True, False, "grid_on"),
        ("ETF Lecture Theatres", "Gidan Kwano", "Behind Senate building", "400+ seats", False, True, False, "gen_on"),
        ("PTDF Computer Center", "Gidan Kwano", "High speed network laboratory", "120+ seats", True, True, True, "gen_on"),
        ("Bosso Reading Room", "Bosso", "Near Old Library building", "180+ seats", False, True, False, "no_power"),
        ("School of Agriculture Hall", "Gidan Kwano", "East campus wing", "150+ seats", False, True, False, "grid_on"),
    ]

    for name, campus, desc, cap, wifi, sockets, ac, status in initial_spots:
        StudySpot.objects.get_or_create(
            name=name,
            defaults={
                'campus': campus,
                'location_desc': desc,
                'capacity_estimate': cap,
                'has_wifi': wifi,
                'has_sockets': sockets,
                'has_ac': ac,
                'current_status': status,
            }
        )

    initial_emergencies = [
        ("Campus Clinic Ambulance (GK)", "clinic", "08031234567", "Gidan Kwano", "24/7 Rapid response ambulance unit"),
        ("Bosso Campus Clinic", "clinic", "08059876543", "Bosso", "Outpatient clinic and emergency triage"),
        ("Main Gate Security Post", "security", "08023456789", "Gidan Kwano", "Chief Security Officer / Patrol unit"),
        ("Bosso Gate Security Post", "security", "08076543210", "Bosso", "Bosso entrance security checkpoint"),
        ("SUG Welfare & Student Affairs", "sug", "08145678901", "Both Campuses", "Student Union Welfare Director helpline"),
        ("State Fire Service (Minna)", "fire", "066-222333", "Minna Metro", "Emergency fire response command"),
    ]

    for title, cat, phone, campus, desc in initial_emergencies:
        EmergencyContact.objects.get_or_create(
            title=title,
            defaults={
                'category': cat,
                'phone_number': phone,
                'campus': campus,
                'description': desc,
            }
        )


def _seed_siwes_companies():
    """Seeds verified top companies accepting IT/SIWES students in Nigeria."""
    companies = [
        ("MainOne Cable Company", "Lagos", "Lagos", "Telecommunications / Cloud", True, "₦50,000 / month", "https://mainone.net", "Careers in network infra, fiber engineering & data centers."),
        ("National Information Technology Development Agency (NITDA)", "Abuja", "FCT", "Government / Tech Policy", True, "Stipend Provided", "https://nitda.gov.ng", "Accepts Computer Science, Cyber Security & Software Eng."),
        ("Julius Berger Nigeria Plc", "Abuja", "FCT", "Civil / Mechanical Engineering", True, "₦40,000 / month", "https://julius-berger.com", "Accepts Civil, Mechanical, Mechatronics, and Building Tech."),
        ("Galaxy Backbone", "Abuja", "FCT", "IT / Cloud / Datacenter", True, "Transport Allowance", "https://galaxybackbone.com.ng", "Excellent for Networking, Server Admin and Telecomms."),
        ("Dangote Sugar & Refinery", "Lagos", "Lagos", "Chemical & Industrial Engineering", True, "₦45,000 / month", "https://dangote.com", "Accepts Chemical, Mechanical and Electrical Engineering."),
        ("National Space Research & Development Agency (NASRDA)", "Abuja", "FCT", "Aerospace / Electronics / Physics", True, "Stipend Provided", "https://nasrda.gov.ng", "Great for Physics, Electrical/Electronics and Remote Sensing."),
    ]

    for name, city, state, ind, takes, stip, web, notes in companies:
        SIWESCompany.objects.get_or_create(
            name=name,
            defaults={
                'city': city,
                'state': state,
                'industry': ind,
                'takes_it_students': takes,
                'stipend_info': stip,
                'website': web,
                'notes': notes,
            }
        )

