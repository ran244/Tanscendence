import logging

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts.models import Friendship, FriendshipStatus
from apps.common.exceptions import BusinessError, ErrorCodes

logger = logging.getLogger("apps.accounts")


def send_friend_request(requester, addressee):
    if requester == addressee:
        raise BusinessError("SELF_FRIENDSHIP", "You cannot add yourself.")
    existing = Friendship.objects.filter(
        Q(requester=requester, addressee=addressee) | Q(requester=addressee, addressee=requester)
    ).first()
    if existing:
        if existing.status == FriendshipStatus.ACCEPTED:
            raise BusinessError("ALREADY_FRIENDS", "You are already friends.")
        if existing.requester_id == requester.id and existing.status == FriendshipStatus.PENDING:
            raise BusinessError("REQUEST_PENDING", "Friend request already sent.")
        if (
            existing.requester_id == addressee.id
            and existing.status == FriendshipStatus.PENDING
        ):
            # reciprocal pending request -> auto-accept
            return _accept(existing, addressee)
        if existing.status == FriendshipStatus.DECLINED:
            existing.delete()
    try:
        with transaction.atomic():
            friendship = Friendship.objects.create(
                requester=requester, addressee=addressee, status=FriendshipStatus.PENDING
            )
    except IntegrityError:
        raise BusinessError("REQUEST_PENDING", "Friend request already sent.")
    return friendship


def _accept(friendship, user):
    with transaction.atomic():
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.save(update_fields=["status", "updated_at"])
    return friendship


def accept_friend_request(user, friendship_id):
    friendship = Friendship.objects.filter(
        pk=friendship_id, addressee=user, status=FriendshipStatus.PENDING
    ).select_related("requester").first()
    if not friendship:
        raise BusinessError(ErrorCodes.NOT_FOUND, "Friend request not found.", 404)
    return _accept(friendship, user)


def decline_friend_request(user, friendship_id):
    friendship = Friendship.objects.filter(
        pk=friendship_id, addressee=user, status=FriendshipStatus.PENDING
    ).first()
    if not friendship:
        raise BusinessError(ErrorCodes.NOT_FOUND, "Friend request not found.", 404)
    friendship.status = FriendshipStatus.DECLINED
    friendship.save(update_fields=["status", "updated_at"])
    return friendship


def remove_friend(user, other_user_id):
    friendship = Friendship.objects.filter(
        Q(requester=user, addressee_id=other_user_id)
        | Q(requester_id=other_user_id, addressee=user),
        status=FriendshipStatus.ACCEPTED,
    ).first()
    if not friendship:
        raise BusinessError(ErrorCodes.NOT_FRIENDS, "Not friends with this user.")
    friendship.delete()
    return True


def list_friends(user):
    return Friendship.objects.filter(
        Q(requester=user) | Q(addressee=user), status=FriendshipStatus.ACCEPTED
    )


def friend_user_ids(user):
    """Ids of the users with whom `user` has an accepted friendship."""
    pairs = list(
        list_friends(user).values_list("requester_id", "addressee_id")
    )
    ids = set()
    for requester_id, addressee_id in pairs:
        if requester_id == user.id:
            ids.add(addressee_id)
        else:
            ids.add(requester_id)
    return list(ids)


def incoming_requests(user):
    return Friendship.objects.filter(
        addressee=user, status=FriendshipStatus.PENDING
    ).select_related("requester")


def outgoing_requests(user):
    return Friendship.objects.filter(
        requester=user, status=FriendshipStatus.PENDING
    ).select_related("addressee")


def friendship_status_between(user_a, user_b):
    friendship = Friendship.objects.filter(
        Q(requester=user_a, addressee=user_b) | Q(requester=user_b, addressee=user_a)
    ).first()
    if not friendship or friendship.status == FriendshipStatus.DECLINED:
        # A declined request leaves no active relationship, matching
        # send_friend_request's own handling of DECLINED rows: it deletes
        # them and lets a fresh request go through.
        return None
    if friendship.status == FriendshipStatus.ACCEPTED:
        return "friends"
    if friendship.requester_id == user_a.id:
        return "pending_outgoing"
    return "pending_incoming"