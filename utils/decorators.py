from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponseForbidden


# decorator
def group_required(*group_names):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user_groups = request.user.groups.values_list("name", flat=True)
            if any(group in user_groups for group in group_names):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden(
                render(request, "global/partials/access_denied.html")
            )

        return _wrapped_view

    return decorator


# deny user
def deny_if_not_in_group(request, *group_names):
    user_groups = request.user.groups.values_list("name", flat=True)
    if not any(group in user_groups for group in group_names):
        return HttpResponseForbidden(
            render(request, "global/partials/access_denied.html")
        )
    return None


# check user groups
def user_is_in_group(request, *group_names):
    user_groups = request.user.groups.values_list("name", flat=True)
    return any(group in user_groups for group in group_names)