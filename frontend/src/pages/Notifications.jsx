import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { get, post } from '../api/client'
import { useAuth } from '../context/AuthContext'

function titleFor(item) {
  const actor = item.actor_username || 'The auction house'
  const target = item.target_id ? ` #${item.target_id}` : ''
  const titles = {
    'notifications.lot_winner': `You won ${item.details?.product_name || `lot${target}`} for $${item.details?.winning_price || '—'}! Complete your order details.`,
    'notifications.lot_ended': item.details?.has_winner
      ? `${item.details.product_name} ended — ${item.details.winner_username} won at $${item.details.winning_price}.`
      : `${item.details?.product_name || `Lot${target}`} ended with no winning bid.`,
    'notifications.cod_confirmed': `${item.details?.buyer_username || actor} submitted delivery details for ${item.details?.product_name || `order${target}`}.`,
    'notifications.order_delivered': `Your order for ${item.details?.product_name || `item${target}`} is complete.`,
    'notifications.support_reply': `Support replied to ticket${target}`,
    'notifications.support_user_reply': `${actor} replied to support ticket${target}`,
    'notifications.support_ticket_created': `${actor} opened support ticket${target}`,
    'notifications.admin_event_submitted': `${actor} submitted auction${target} for review`,
    'notifications.event_cancellation_requested': `${actor} requested auction cancellation${target}`,
    'notifications.event_cancellation_approved': `Your auction cancellation was approved`,
    'notifications.event_cancellation_rejected': `Your auction cancellation was rejected`,
    'notifications.ticket_status_changed': `Support ticket${target} status changed`,
    'notifications.event_approved': `Auction${target} was approved`,
    'notifications.event_rejected': `Auction${target} was rejected`,
    'notifications.friend_request': `${actor} sent you a friend request`,
    'notifications.friend_accepted': `${actor} accepted your friend request`,
    'notifications.direct_message': `${actor} sent you a message`,
  }
  return titles[item.message_key] || item.verb.replaceAll('_', ' ').toLowerCase().replace(/^./, (letter) => letter.toUpperCase())
}

function destinationFor(item, isAdmin) {
  if (item.target_type === 'supportticket') return isAdmin ? '/admin?section=support' : `/report-issue?ticket=${item.target_id}`
  if (item.target_type === 'auctioncancellationrequest') return isAdmin ? '/admin?section=cancellations' : '/my-auctions'
  if (item.target_type === 'auctionevent') return isAdmin ? '/admin?section=approvals' : '/my-auctions'
  if (item.verb === 'FRIEND_REQUEST' || item.verb === 'FRIEND_ACCEPTED') return '/friends'
  if (item.verb === 'DIRECT_MESSAGE' && item.actor_id) return `/friends/${item.actor_id}/chat`
  if (item.verb === 'LOT_WINNER') return '/orders'
  if (['LOT_ENDED', 'COD_CONFIRMED'].includes(item.verb)) return '/sales'
  if (item.target_type === 'order') return `/orders/${item.target_id}`
  return null
}

export default function Notifications() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState([])
  const [error, setError] = useState('')
  const load = () => get('/notifications/?page_size=100').then((data) => setItems(data.results || [])).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])

  const open = async (item) => {
    try {
      if (!item.is_read) await post(`/notifications/${item.id}/read/`)
      const destination = destinationFor(item, user?.role === 'ADMIN')
      if (destination) navigate(destination)
      else load()
    } catch (err) { setError(err.message) }
  }
  const readAll = async () => { try { await post('/notifications/read-all/'); await load() } catch (err) { setError(err.message) } }
  const hasUnread = items.some((item) => !item.is_read)

  return (
    <Layout>
      <section className="notifications-page">
        <div className="notifications-heading">
          <div>
            <h2>Notifications</h2>
            {user?.role === 'ADMIN' && <p className="sub">Actionable activity from users appears here.</p>}
          </div>
          <button
            aria-label="Mark all notifications as read"
            className="btn btn-ghost notifications-read-all"
            disabled={!hasUnread}
            onClick={readAll}
            type="button"
          >
            Mark all as read
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
        {items.length === 0 ? (
          <div className="empty-state"><h3>You’re all caught up</h3></div>
        ) : items.map((item) => (
          <button
            key={item.id}
            className="list-row"
            style={{ width: '100%', textAlign: 'left', opacity: item.is_read ? .65 : 1 }}
            onClick={() => open(item)}
          >
            <div className="flex1">
              <h4>{titleFor(item)}</h4>
              <div className="sub">{new Date(item.created_at).toLocaleString()}</div>
            </div>
            {!item.is_read && <span className="tag tag-live">New</span>}
          </button>
        ))}
      </section>
    </Layout>
  )
}
