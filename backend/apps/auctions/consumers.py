import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from apps.auctions.models import (
    AuctionEventStatus,
    AuctionLot,
    AuctionLotStatus,
    BidStatus,
)

logger = logging.getLogger("apps.auctions")


def _lot_snapshot(lot):
    return {
        "id": lot.id,
        "current_price": str(lot.current_price),
        "minimum_next_bid": str(lot.minimum_next_bid),
        "bid_count": lot.bids.filter(status=BidStatus.ACCEPTED).count(),
        "status": lot.status,
        "server_time": timezone.now().isoformat(),
    }


class LotConsumer(AsyncJsonWebsocketConsumer):
    """
    Per-lot live channel. Anyone may connect (public auction data); personal
    events still travel on the authenticated `user_<id>` channel.
    Group name: `lot_<id>`.
    """

    async def connect(self):
        self.lot_id = self.scope["url_route"]["kwargs"]["lot_id"]
        self.group_name = f"lot_{self.lot_id}"
        self.lot_exists = await database_sync_to_async(
            AuctionLot.objects.filter(
                pk=self.lot_id,
                auction_event__status__in=[
                    AuctionEventStatus.SCHEDULED,
                    AuctionEventStatus.ACTIVE,
                    AuctionEventStatus.ENDED,
                ],
                status__in=[
                    AuctionLotStatus.SCHEDULED,
                    AuctionLotStatus.ACTIVE,
                    AuctionLotStatus.SOLD,
                    AuctionLotStatus.UNSOLD,
                ],
            ).exists
        )()
        if not self.lot_exists:
            await self.close(code=4404)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await database_sync_to_async(self._snapshot)()
        await self.send_json({"type": "snapshot", **snapshot})

    def _snapshot(self):
        lot = AuctionLot.objects.select_related("auction_event").get(pk=self.lot_id)
        return _lot_snapshot(lot)

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type")
        if kind == "ping":
            await self.send_json({"type": "pong"})
        elif kind == "resync":
            snapshot = await database_sync_to_async(self._snapshot)()
            await self.send_json({"type": "snapshot", **snapshot})
        else:
            await self.send_json({"type": "error", "code": "UNKNOWN_MESSAGE_TYPE"})

    # -- broadcast handlers ------------------------------------------------
    async def bid_accepted(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "bid.accepted", **payload})

    async def lot_ended(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "lot.ended", **payload})


class BrowseConsumer(AsyncJsonWebsocketConsumer):
    """Live browse updates (public price/status changes). Group: `browse_lots`."""

    async def connect(self):
        self.group_name = "browse_lots"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "welcome", "channel": "browse_lots"})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def lot_price_update(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "lot.price_update", **payload})

    async def event_activated(self, event):
        payload = dict(event)
        payload.pop("type", None)
        await self.send_json({"type": "event.activated", **payload})
