from django.urls import path
from users import views

urlpatterns = [
    path("", views.home, name="home"),
    path("logout/", views.logout_action, name="logout"),
    path("login/", views.login_action, name="login"),
    path("mfa/", views.mfa, name="mfa"),
    path("profile/", views.profile, name="profile"),
    path("edit/", views.edit_action, name="edit"),
    path("change_password/", views.change_password, name="change_password"),
]
