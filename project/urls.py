from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path, re_path
from django.views.static import serve

BASE_URL = "app"

urlpatterns = [
    path(f"{BASE_URL}/admin/", admin.site.urls),
    path("", lambda request: redirect(f"/{BASE_URL}/", permanent=True)),
    path(f"{BASE_URL}/", include("users.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(
            r"^app/static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}
        ),
    ]