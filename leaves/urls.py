from django.urls import path
from leaves import views


urlpatterns = [
    path("", views.leaves_view, name="leaves_view"),
    path("create/", views.leave_create, name="leave_create"),
    path("create/<int:user_id>/", views.leave_create, name="leave_create_id"),
    path("edit/<int:user_id>/<int:leave_id>/", views.leave_edit, name="leave_edit"),
    path("history/active/<int:user_id>/", views.leaves_active_history, name="leaves_active_history"),  # active leaves history
    path("history/interrupted/<int:user_id>/", views.leaves_interrupted_history, name="leaves_interrupted_history"),  # interrupted leaves history
    path("interrupt/<int:user_id>/<int:leave_id>/", views.leave_interrupt, name="leave_interrupt"),  # to interrupt an active leave
    path("resume/<int:user_id>/<int:leave_id>/", views.leave_resume, name="leave_resume"),  # to resume an interrupted leave
]
