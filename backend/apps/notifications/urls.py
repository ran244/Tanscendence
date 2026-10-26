from django.urls import path

from apps.notifications import views

urlpatterns = [
    path("chats/<int:user_id>/", views.direct_messages, name="direct_messages"),
    path("", views.notification_list, name="notification_list"),
    path("unread-count/", views.notification_unread_count, name="notification_unread_count"),
    path("<int:notification_id>/read/", views.notification_read, name="notification_read"),
    path("read-all/", views.notification_read_all, name="notification_read_all"),
    path("support/tickets/", views.tickets, name="tickets"),
    path("support/tickets/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("admin/support/tickets/", views.admin_tickets, name="admin_tickets"),
    path(
        "admin/support/tickets/<int:ticket_id>/",
        views.admin_ticket_status,
        name="admin_ticket_status",
    ),
]
