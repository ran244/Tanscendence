from apps.accounts.models import Friendship, FriendshipStatus
from apps.common.tests_base import BaseTestCase
from apps.notifications.models import DirectMessage, Notification, NotificationVerb


class DirectMessageApiTests(BaseTestCase):
    def setUp(self):
        self.alice = self.create_user("chat_alice")
        self.bob = self.create_user("chat_bob")

    def test_only_friends_can_send_and_receive_messages(self):
        self.api_login(self.alice)
        denied = self.api_post(f"/api/notifications/chats/{self.bob.id}/", {"message": "Hello"})
        self.assertEqual(denied.status_code, 403)

        Friendship.objects.create(requester=self.alice, addressee=self.bob, status=FriendshipStatus.ACCEPTED)
        sent = self.api_post(f"/api/notifications/chats/{self.bob.id}/", {"message": "Hello Bob"})
        self.assertEqual(sent.status_code, 201, sent.data)
        self.assertEqual(DirectMessage.objects.get().message, "Hello Bob")
        self.assertTrue(Notification.objects.filter(recipient=self.bob, verb=NotificationVerb.DIRECT_MESSAGE).exists())

        self.api_login(self.bob)
        thread = self.client.get(f"/api/notifications/chats/{self.alice.id}/")
        self.assertEqual(thread.status_code, 200)
        self.assertEqual(thread.data["results"][0]["message"], "Hello Bob")
