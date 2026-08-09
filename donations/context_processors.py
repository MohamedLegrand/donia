def notifications(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return {
            'unread_notifications_count': user.notifications.filter(is_read=False).count()
        }
    return {'unread_notifications_count': 0}
