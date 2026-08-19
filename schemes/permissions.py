from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import CustomUser


def owner_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.role == CustomUser.Role.OWNER):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped
