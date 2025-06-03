from django.urls import path
from users import views


urlpatterns = [
    path("", views.home, name="home"),  # home page
    path("logout/", views.logout_action, name="logout"),  # log out user
    path("login/", views.login_action, name="login"),  # login page and login action
    path("mfa/", views.mfa, name="mfa"),  # activate on profile page or verify during login
    path("profile/", views.profile, name="profile"),  # profile page
    path("edit/<int:user_id>", views.edit, name="edit_id"),  # edit another user
    path("edit/", views.edit, name="edit"),  # edit own data
    path("register/", views.register, name="register"),  # register user
    path("active_users/", views.active_users, name="active_users"),  # active users list
    path("deactivated_users/", views.deactivated_users, name="deactivated_users"),  # deactivated users list
    path("activate_user/<int:user_id>/", views.activate_user, name="activate_user"),  # activate deactivated user
    path("deactivate_user/<int:user_id>/", views.deactivate_user, name="deactivate_user"),  # deactivate active user
    # path("disable_mfa/<int:user_id>/", views.disable_mfa, name="disable_mfa"),  # disable user's mfa
    # path("reset_user_password/<int:user_id>/", views.reset_user_password, name="reset_user_password"),  # reset user's password
    path("change_password/", views.change_password, name="change_password"),  # change own password
    # path("senha/redefinir/<str:token>/", views.redefinir_senha, name="redefinir_senha"),  # reset via email
    # path("senha/esqueci/", views.solicitar_reset_senha, name="solicitar_reset_senha"),  # request reset via email
]