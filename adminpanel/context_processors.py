from accounts.models import User


def pending_approvals(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated and user.is_admin_role:
        return {
            'admin_pending_count': User.objects.filter(
                role=User.Role.RESPONSABLE, is_approved=False, onboarding_completed=True
            ).count()
        }
    return {'admin_pending_count': 0}
