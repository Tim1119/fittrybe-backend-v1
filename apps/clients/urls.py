from django.urls import path

from . import views

urlpatterns = [
    path("", views.ClientListView.as_view(), name="client-list"),
    path("<int:pk>/", views.ClientDetailView.as_view(), name="client-detail"),
    path(
        "<int:pk>/reminder/",
        views.ClientReminderView.as_view(),
        name="client-reminder",
    ),
    path("invite/", views.InviteCreateListView.as_view(), name="invite-list"),
    path(
        "invite/<str:token>/",
        views.InviteDeactivateView.as_view(),
        name="invite-deactivate",
    ),
    path(
        "invite/<str:token>/preview/",
        views.InvitePreviewView.as_view(),
        name="invite-preview",
    ),
    path(
        "invite/<str:token>/accept/",
        views.InviteAcceptView.as_view(),
        name="invite-accept",
    ),
    path("search/", views.ClientSearchView.as_view(), name="client-search"),
    path("add/", views.ClientDirectAddView.as_view(), name="client-direct-add"),
]
