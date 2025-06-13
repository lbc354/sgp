from django.urls import path
from demands import views


urlpatterns = [
    path("", views.demands_view, name="demands_view"),
    path("completed/", views.demands_completed_view, name="demands_completed_view"),
    path("create/", views.demand_create, name="demand_create"),
    # path("edit/<int:demand_id>/", views.demand_edit, name="demand_edit"),
    # path("conclude/<int:demand_id>/", views.demand_conclude, name="demand_conclude"),
    # path("restore/<int:demand_id>/", views.demand_restore, name="demand_restore"),
    # path("history/<int:demand_id>/<int:history_id>/", views.demand_history_details, name="demand_history_details"),
    # path("history/<int:demand_id>/", views.demand_history, name="demand_history"),
]
