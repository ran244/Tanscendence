from apps.common.tests_base import BaseTestCase
from apps.notifications.models import (
    Notification,
    NotificationVerb,
    SupportMessage,
    SupportTicket,
    TicketStatus,
)
from rest_framework.test import APIClient


class NotificationAndSupportTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user("notifyuser")
        self.other = self.create_user("notifyother")

    def test_user_cannot_mark_another_users_notification_read(self):
        notification = Notification.objects.create(
            recipient=self.other, verb="BID_ACCEPTED", message_key="test"
        )
        self.api_login(self.user)
        response = self.api_post(f"/api/notifications/{notification.pk}/read/")
        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)

    def test_closed_ticket_rejects_new_replies(self):
        ticket = SupportTicket.objects.create(
            reporter=self.user, subject="Question", message="Help", status=TicketStatus.CLOSED
        )
        self.api_login(self.user)
        response = self.api_post(
            f"/api/notifications/support/tickets/{ticket.pk}/", {"message": "Again"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ticket.messages.count(), 0)

    def test_new_ticket_notifies_every_active_admin(self):
        first_admin = self.create_admin("support_admin_one")
        second_admin = self.create_admin("support_admin_two")
        inactive_admin = self.create_admin("inactive_support_admin")
        inactive_admin.is_active = False
        inactive_admin.save(update_fields=["is_active"])
        self.api_login(self.user)

        response = self.api_post(
            "/api/notifications/support/tickets/",
            {"subject": "Broken page", "message": "The page is blank."},
        )
        self.assertEqual(response.status_code, 201, response.data)
        ticket = SupportTicket.objects.get(pk=response.data["id"])
        notifications = Notification.objects.filter(
            verb=NotificationVerb.SUPPORT_TICKET_CREATED,
            target_object_id=ticket.pk,
        )
        self.assertSetEqual(
            set(notifications.values_list("recipient_id", flat=True)),
            {first_admin.pk, second_admin.pk},
        )
        self.assertFalse(notifications.filter(recipient=inactive_admin).exists())
        self.assertTrue(notifications.filter(actor=self.user).exists())

    def test_admin_reply_is_visible_in_ticket_and_notifies_reporter(self):
        user_client = APIClient()
        admin_client = APIClient()
        admin = self.create_admin("reply_admin")
        self.api_login(self.user, client=user_client)
        created = self.api_post(
            "/api/notifications/support/tickets/",
            {"subject": "Auction question", "message": "Please help."},
            client=user_client,
        )
        ticket_id = created.data["id"]
        self.api_login(admin, client=admin_client)
        reply = self.api_post(
            f"/api/notifications/support/tickets/{ticket_id}/",
            {"message": "We reviewed your issue and fixed it."},
            client=admin_client,
        )
        self.assertEqual(reply.status_code, 201, reply.data)

        notification = Notification.objects.get(
            recipient=self.user,
            verb=NotificationVerb.SUPPORT_REPLY,
            target_object_id=ticket_id,
        )
        self.assertEqual(notification.actor, admin)
        self.assertIsNone(notification.read_at)
        self.assertEqual(
            SupportMessage.objects.filter(ticket_id=ticket_id, author=admin).count(),
            1,
        )

        listing = user_client.get("/api/notifications/support/tickets/?page_size=100")
        self.assertEqual(listing.status_code, 200, listing.data)
        messages = listing.data["results"][0]["messages"]
        self.assertEqual([row["author_username"] for row in messages], [self.user.username, admin.username])
        self.assertEqual(messages[-1]["message"], "We reviewed your issue and fixed it.")

    def test_user_follow_up_notifies_admin_but_not_the_reporter(self):
        admin = self.create_admin("followup_admin")
        self.api_login(self.user)
        created = self.api_post(
            "/api/notifications/support/tickets/",
            {"subject": "More details", "message": "Initial report."},
        )
        response = self.api_post(
            f"/api/notifications/support/tickets/{created.data['id']}/",
            {"message": "Here is another detail."},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(
            Notification.objects.filter(
                recipient=admin,
                verb=NotificationVerb.SUPPORT_REPLY,
                message_key="notifications.support_user_reply",
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.user,
                verb=NotificationVerb.SUPPORT_REPLY,
            ).exists()
        )
