from .models import DirectMessage


def dm_unread(request):
    if not request.user.is_authenticated:
        return {}
    return {'dm_unread_count': DirectMessage.objects.filter(recipient=request.user, read_at__isnull=True).count()}
