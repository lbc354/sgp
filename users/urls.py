from django.urls import path
from users import views


urlpatterns = [
    path("", views.home, name="home"),
    path("logout/", views.logout_action, name="logout"),
    path("login/", views.login_action, name="login"),
    path("mfa/", views.mfa, name="mfa"),
    path("profile/", views.profile, name="profile"),
    path("edit/<int:user_id>", views.edit, name="edit_id"),  # edit another user
    path("edit/", views.edit, name="edit"),  # edit own data
    path("register/", views.register, name="register"),
    path("active_users/", views.active_users, name="active_users"),
    path("deactivated_users/", views.deactivated_users, name="deactivated_users"),
    path("activate_user/<int:user_id>/", views.activate_user, name="activate_user"),
    path("deactivate_user/<int:user_id>/", views.deactivate_user, name="deactivate_user"),
    path("disable_mfa/<int:user_id>/", views.disable_mfa, name="disable_mfa"),
    path("reset_user_password/<int:user_id>/", views.reset_user_password, name="reset_user_password"),  # reset user's password
    path("reset_password/", views.reset_password, name="reset_password"),  # reset via form
    path("password_reset/<str:token>/", views.password_reset, name="password_reset"),  # reset via email
    path("request_password_reset/", views.request_password_reset, name="request_password_reset"),  # request reset via email
]