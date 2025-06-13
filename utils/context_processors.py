# usage example of context_processors (/project/settings.py)
from users.models import CustomUser


def users_count(request):
    users_qt = CustomUser.objects.filter(is_superuser=False).count()
    return {"users_qt": users_qt}
