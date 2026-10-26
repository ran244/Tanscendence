import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Layout from '../components/Layout'
import AdminBidTracking from '../components/AdminBidTracking'
import { del, get, patch, post } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { formatMoney } from '../utils/money'

const sections = ['overview', 'pending-bids', 'active-bids', 'auctions', 'users', 'support', 'categories']
const HISTORY_PAGE_SIZE = 20
const historyTagClasses = {
  APPROVED: 'tag-approved',
  SCHEDULED: 'tag-approved',
  ACTIVE: 'tag-live',
  AWAITING_ORDERS: 'tag-pending',
  ENDED: 'tag-ended',
  REJECTED: 'tag-rejected',
  CANCELLED: 'tag-cancelled',
  PENDING_APPROVAL: 'tag-pending',
}
const totalLabels = {
  events: 'Total event records',
  lots: 'Total lot records',
  bids: 'Accepted bids',
  sold: 'Sold lots',
  unsold: 'Unsold lots',
  revenue: 'Delivered revenue',
  revenue_paid: 'Revenue collected',
  orders: 'Orders',
  users: 'Users',
}

function Empty({ children }) {
  return <div className="empty-state"><p>{children}</p></div>
}

export default function AdminDashboard() {
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedSection = searchParams.get('section')
  const [section, setSection] = useState(() => sections.includes(requestedSection) ? requestedSection : 'overview')
  const [auctionFilter, setAuctionFilter] = useState('ALL')
  const [auctionSearch, setAuctionSearch] = useState('')

  const changeSection = (newSection) => {
    setSection(newSection)
    setSearchParams({ section: newSection })
  }
  const [events, setEvents] = useState([])
  const [rejectedEvents, setRejectedEvents] = useState([])
  const [historyPage, setHistoryPage] = useState({ count: 0, page: 1, total_pages: 1, results: [] })
  const [historyPageNumber, setHistoryPageNumber] = useState(1)
  const [cancellationRequests, setCancellationRequests] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [users, setUsers] = useState([])
  const [tickets, setTickets] = useState([])
  const [categories, setCategories] = useState([])
  const [userSearch, setUserSearch] = useState('')
  const [ticketFilter, setTicketFilter] = useState('')
  const [categoryName, setCategoryName] = useState('')
  const [ticketReplies, setTicketReplies] = useState({})
  const [rejecting, setRejecting] = useState(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const query = ticketFilter ? `?status=${ticketFilter}&page_size=100` : '?page_size=100'
      const [eventPage, rejectedPage, auctionHistoryPage, cancellationPage, dashboard, userPage, ticketPage, categoryPage] = await Promise.all([
        get('/auctions/admin/events/?status=PENDING_APPROVAL&page_size=100'),
        get('/auctions/admin/events/?status=REJECTED&page_size=100'),
        get(`/auctions/admin/events/history/?page=${historyPageNumber}&page_size=${HISTORY_PAGE_SIZE}`),
        get('/auctions/admin/cancellation-requests/?status=PENDING&page_size=100'),
        get('/analytics/dashboard/'),
        get('/accounts/admin/users/'),
        get(`/notifications/admin/support/tickets/${query}`),
        get('/products/categories/?page_size=100'),
      ])
      setEvents(eventPage.results || [])
      setRejectedEvents(rejectedPage.results || [])
      setHistoryPage(auctionHistoryPage)
      setCancellationRequests(cancellationPage.results || [])
      setAnalytics(dashboard)
      setUsers(userPage.results || [])
      setTickets(ticketPage.results || [])
      setCategories(categoryPage.results || categoryPage || [])
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [historyPageNumber, ticketFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (sections.includes(requestedSection)) setSection(requestedSection)
  }, [requestedSection])

  const run = async (key, action, success) => {
    setBusy(key); setError(''); setNotice('')
    try { await action(); setNotice(success); await load(); return true }
    catch (err) { setError(err.message) }
    finally { setBusy('') }
    return false
  }

  const approve = (event) => run(`event-${event.id}`, () => post(`/auctions/admin/events/${event.id}/approve/`), `“${event.title}” was approved.`)
  const reject = (event) => {
    if (!reason.trim()) { setError('A rejection reason is required.'); return }
    run(`event-${event.id}`, () => post(`/auctions/admin/events/${event.id}/reject/`, { reason: reason.trim() }), `“${event.title}” was rejected.`)
    setRejecting(null); setReason('')
  }
  const approveCancellation = (request) => run(`cancellation-${request.id}`, () => post(`/auctions/admin/cancellation-requests/${request.id}/approve/`), `Cancellation of “${request.event_title}” was approved.`)
  const rejectCancellation = (request) => {
    const rejectionReason = window.prompt(`Why are you rejecting cancellation of “${request.event_title}”?`)?.trim()
    if (rejectionReason) run(`cancellation-${request.id}`, () => post(`/auctions/admin/cancellation-requests/${request.id}/reject/`, { reason: rejectionReason }), `Cancellation of “${request.event_title}” was rejected.`)
  }
  const saveUser = (target, fields, message) => run(`user-${target.id}`, () => patch(`/accounts/admin/users/${target.id}/`, fields), message)
  const toggleBlock = (target) => {
    if (target.is_blocked) return run(`user-${target.id}`, () => post(`/accounts/admin/users/${target.id}/unblock/`), `${target.username} can bid again.`)
    const blockReason = window.prompt(`Why are you blocking ${target.username} from bidding?`)?.trim()
    if (blockReason) run(`user-${target.id}`, () => post(`/accounts/admin/users/${target.id}/block/`, { reason: blockReason }), `${target.username} was blocked from bidding.`)
  }
  const updateTicket = (ticket, status) => run(`ticket-${ticket.id}`, () => patch(`/notifications/admin/support/tickets/${ticket.id}/`, { status }), `Ticket #${ticket.id} is now ${status.toLowerCase().replace('_', ' ')}.`)
  const replyToTicket = async (event, ticket) => { event.preventDefault(); const message = ticketReplies[ticket.id]?.trim(); if (message && await run(`ticket-${ticket.id}`, () => post(`/notifications/support/tickets/${ticket.id}/`, { message }), `Reply sent on ticket #${ticket.id}.`)) setTicketReplies((old) => ({ ...old, [ticket.id]: '' })) }
  const createCategory = async (event) => { event.preventDefault(); if (categoryName.trim() && await run('category-new', () => post('/products/categories/', { name: categoryName.trim() }), 'Category created.')) setCategoryName('') }
  const removeCategory = (category) => { if (window.confirm(`Delete category “${category.name}”? This only works when it is unused.`)) run(`category-${category.id}`, () => del(`/products/categories/${category.id}/`), 'Category deleted.') }
  const renameCategory = (category) => { const name = window.prompt('New category name', category.name)?.trim(); if (name && name !== category.name) run(`category-${category.id}`, () => patch(`/products/categories/${category.id}/`, { name }), 'Category renamed.') }

  const visibleUsers = users.filter((target) => `${target.username} ${target.email} ${target.role}`.toLowerCase().includes(userSearch.toLowerCase()))
  const historyEvents = historyPage.results || []
  const auctionSearchTerm = auctionSearch.trim().toLowerCase()
  const visibleAuctionEvents = (auctionFilter === 'PENDING' ? events : historyEvents)
    .filter((event) => {
      if (auctionFilter === 'ALL') return true
      if (auctionFilter === 'APPROVED') return ['APPROVED', 'SCHEDULED', 'ACTIVE', 'ENDED'].includes(event.status)
      if (auctionFilter === 'AWAITING_ORDERS') return event.status === 'AWAITING_ORDERS'
      if (auctionFilter === 'REJECTED') return event.status === 'REJECTED'
      if (auctionFilter === 'CANCELLED') return event.status === 'CANCELLED'
      if (auctionFilter === 'PENDING') return event.status === 'PENDING_APPROVAL'
      return true
    })
    .filter((event) => !auctionSearchTerm || event.title.toLowerCase().includes(auctionSearchTerm))
  const totals = analytics?.totals || {}
  const pendingSections = [
    { label: 'Auction Approvals', items: events, empty: 'No pending auction approvals.' },
    { label: 'Cancellation Requests', items: cancellationRequests, empty: 'No pending cancellation requests.' },
  ].filter(({ items }) => items.length > 0)
  const hasPendingRequests = events.length > 0 || cancellationRequests.length > 0

  return <Layout><section className="admin-page">
    <div className="admin-heading"><div><span className="eyebrow">Platform control center</span><h1>Admin workspace</h1><p>Review auctions, manage accounts and resolve support requests.</p></div><button className="btn btn-outline btn-sm" onClick={load} disabled={loading}>{loading ? 'Refreshing…' : 'Refresh data'}</button></div>
    <nav className="admin-tabs" aria-label="Administration sections">
      {sections.map((name) => (
        <button
          key={name}
          className={section === name ? 'active' : ''}
          onClick={() => changeSection(name)}
        >
          {name === 'pending-bids'
            ? `Pending Auctions (${events.length})`
            : name === 'active-bids'
            ? 'Live Bid Tracking'
            : name === 'auctions'
            ? `Auctions (${historyPage.count || 0})`
            : name.charAt(0).toUpperCase() + name.slice(1)}
        </button>
      ))}
    </nav>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="admin-notice" role="status">{notice}</p>}
    {loading && !analytics ? <Empty>Loading administrator data…</Empty> : <>
      {section === 'overview' && <div className="admin-section"><h2>Platform overview</h2><p>Record totals include private drafts, rejected submissions, cancelled auctions, and completed auctions; they are not counts of currently live auctions.</p><div className="stats-grid">{Object.entries(totals).map(([key, value]) => <div className="panel admin-stat" key={key}><span>{totalLabels[key] || key.replaceAll('_', ' ')}</span><strong>{value}</strong></div>)}</div><div className="admin-summary-grid"><button onClick={() => changeSection('pending-bids')}><strong>{events.length + cancellationRequests.length}</strong><span>pending submissions / cancellations</span></button><button onClick={() => changeSection('active-bids')}><strong>Live</strong><span>track active auction bids</span></button><button onClick={() => changeSection('support')}><strong>{tickets.filter((ticket) => ticket.status === 'OPEN').length}</strong><span>open support tickets</span></button><button onClick={() => changeSection('users')}><strong>{users.filter((target) => target.is_blocked).length}</strong><span>blocked bidders</span></button></div></div>}

      {section === 'pending-bids' && (
        <div className="admin-section">
          <h2>Pending Auctions & Requests</h2>
          <p>Review submitted auctions for approval or rejection, and any cancellation requests that still need action.</p>

          {!hasPendingRequests ? (
            <Empty>No pending requests.</Empty>
          ) : pendingSections.map(({ label, items, empty }) => (
            <div key={label}>
              <h3 style={{ marginTop: 24, marginBottom: 12 }}>{label} ({items.length})</h3>
              {items.length === 0 ? <Empty>{empty}</Empty> : (
                items.map((event) => (
                  label === 'Auction Approvals' ? (
                    <article className="admin-card" key={event.id}><div className="admin-card-head"><div><span className="tag tag-upcoming">{event.status_display}</span><h3>{event.title}</h3><p>Submitted by <strong>{event.organizer_username}</strong> · {new Date(event.submitted_at).toLocaleString()}</p></div><div className="admin-actions"><button className="btn btn-primary btn-sm" disabled={busy === `event-${event.id}`} onClick={() => approve(event)}>Approve</button><button className="btn btn-outline btn-sm" disabled={busy === `event-${event.id}`} onClick={() => { setRejecting(event.id); setReason('') }}>Reject</button></div></div><p>{event.description}</p><dl className="admin-meta"><div><dt>Starts</dt><dd>{new Date(event.start_time).toLocaleString()}</dd></div><div><dt>Ends</dt><dd>{new Date(event.end_time).toLocaleString()}</dd></div><div><dt>Lots</dt><dd>{event.lots.length}</dd></div></dl><div className="admin-lots">{event.lots.map((lot) => <div key={lot.id}><img src={lot.product_image || '/placeholder.svg'} alt=""/><span><strong>Lot {lot.lot_number}: {lot.product_name}</strong><small>Starts at ${lot.starting_price} · increment ${lot.minimum_increment}</small></span></div>)}</div>{rejecting === event.id && <div className="admin-reject"><label htmlFor={`reason-${event.id}`}>Reason sent to seller</label><textarea id={`reason-${event.id}`} className="textarea" value={reason} onChange={(e) => setReason(e.target.value)} required/><div className="admin-actions"><button className="btn btn-outline btn-sm" onClick={() => setRejecting(null)}>Cancel</button><button className="btn btn-primary btn-sm" onClick={() => reject(event)}>Confirm rejection</button></div></div>}</article>
                  ) : (
                    <article className="admin-card" key={event.id}><div className="admin-card-head"><div><span className="tag tag-upcoming">Pending</span><h3>{event.event_title}</h3><p>Requested by <strong>{event.requester_username}</strong> · {new Date(event.created_at).toLocaleString()}</p></div><div className="admin-actions"><button className="btn btn-primary btn-sm" disabled={busy === `cancellation-${event.id}`} onClick={() => approveCancellation(event)}>Approve cancellation</button><button className="btn btn-outline btn-sm" disabled={busy === `cancellation-${event.id}`} onClick={() => rejectCancellation(event)}>Reject</button></div></div><dl className="admin-meta"><div><dt>Auction starts</dt><dd>{new Date(event.event_start_time).toLocaleString()}</dd></div><div><dt>Current status</dt><dd>{event.event_status}</dd></div><div><dt>Request</dt><dd>#{event.id}</dd></div></dl><div className="admin-rejection-record"><strong>Seller’s cancellation reason</strong><p>{event.reason}</p></div></article>
                  )
                ))
              )}
            </div>
          ))}
        </div>
      )}

      {section === 'active-bids' && <AdminBidTracking />}

      {section === 'auctions' && (
        <div className="admin-section">
          <div className="admin-section-head">
            <div>
              <h2>Auctions</h2>
              <p>Filter and view all platform auctions by status.</p>
            </div>
            <div className="admin-auction-controls">
              <input className="input admin-search" type="search" placeholder="Search auction name" aria-label="Search auctions by name" value={auctionSearch} onChange={(e) => setAuctionSearch(e.target.value)} />
              <select className="input admin-search" aria-label="Filter auctions by status" value={auctionFilter} onChange={(e) => { setAuctionFilter(e.target.value); setHistoryPageNumber(1) }}>
                <option value="ALL">All auctions</option>
                <option value="APPROVED">Approved</option>
                <option value="AWAITING_ORDERS">Waiting for order completion</option>
                <option value="REJECTED">Rejected</option>
                <option value="CANCELLED">Cancelled</option>
                <option value="PENDING">Pending auctions</option>
              </select>
            </div>
          </div>

          {visibleAuctionEvents.map((event) => (
              <article className="admin-card" key={event.id}>
                <div className="admin-card-head">
                  <div>
                    <span className={`tag ${historyTagClasses[event.status] || 'tag-ended'}`}>{event.status_display}</span>
                    <h3>{event.title}</h3>
                    <p>Created by <strong>{event.organizer_username}</strong> · updated {new Date(event.updated_at).toLocaleString()}</p>
                  </div>
                </div>
                <p>{event.description}</p>
                <dl className="admin-meta">
                  <div><dt>Starts</dt><dd>{new Date(event.start_time).toLocaleString()}</dd></div>
                  <div><dt>Ends</dt><dd>{new Date(event.end_time).toLocaleString()}</dd></div>
                  <div><dt>Lots</dt><dd>{event.lots.length}</dd></div>
                </dl>
                <div className="admin-lots">
                  {event.lots.map((lot) => (
                    <div key={lot.id}>
                      <img src={lot.product_image || '/placeholder.svg'} alt="" />
                      <span>
                        <strong>Lot {lot.lot_number}: {lot.product_name}</strong>
                        <small>
                          {lot.winner_username
                            ? `Winner ${lot.winner_username} · winning price ${formatMoney(lot.current_price)}`
                            : 'No winning bid'}
                          {' · '}{lot.order_status_display || lot.status.replaceAll('_', ' ').toLowerCase()}
                        </small>
                      </span>
                    </div>
                  ))}
                </div>
              </article>
            ))}

          {visibleAuctionEvents.length === 0 && <Empty>No auctions match this filter and search.</Empty>}

          {auctionFilter !== 'PENDING' && !auctionSearchTerm && historyPage.total_pages > 1 && (
            <nav className="admin-pagination" aria-label="Auction history pages">
              <button className="btn btn-outline btn-sm" disabled={!historyPage.previous || loading} onClick={() => setHistoryPageNumber((page) => Math.max(1, page - 1))}>Previous</button>
              <span>Page {historyPage.page} of {historyPage.total_pages}</span>
              <button className="btn btn-outline btn-sm" disabled={!historyPage.next || loading} onClick={() => setHistoryPageNumber((page) => page + 1)}>Next</button>
            </nav>
          )}
        </div>
      )}

      {section === 'users' && <div className="admin-section"><div className="admin-section-head"><div><h2>User management</h2><p>Change platform roles, activate accounts and control bidding access.</p></div><input className="input admin-search" placeholder="Search users" aria-label="Search users" value={userSearch} onChange={(e) => setUserSearch(e.target.value)}/></div>{visibleUsers.map((target) => <div className="admin-user" key={target.id}><div><strong>{target.username}</strong><span>{target.email}</span><small>Joined {new Date(target.date_joined).toLocaleDateString()} · {target.last_login ? `last login ${new Date(target.last_login).toLocaleDateString()}` : 'never logged in'}</small></div><select className="input" aria-label={`Role for ${target.username}`} value={target.role} disabled={target.id === user.id || busy === `user-${target.id}`} onChange={(e) => saveUser(target, { role: e.target.value }, `${target.username}'s role was updated.`)}><option value="USER">User</option><option value="ADMIN">Admin</option></select><button className="btn btn-outline btn-sm" disabled={target.id === user.id || busy === `user-${target.id}`} onClick={() => saveUser(target, { is_active: !target.is_active }, `${target.username} is now ${target.is_active ? 'inactive' : 'active'}.`)}>{target.is_active ? 'Deactivate' : 'Activate'}</button><button className="btn btn-outline btn-sm" disabled={target.id === user.id || busy === `user-${target.id}`} onClick={() => toggleBlock(target)}>{target.is_blocked ? 'Unblock bidding' : 'Block bidding'}</button></div>)}</div>}

      {section === 'support' && <div className="admin-section"><div className="admin-section-head"><div><h2>Support tickets</h2><p>Reply to, track and resolve reports submitted by users.</p></div><select className="input admin-search" value={ticketFilter} onChange={(e) => setTicketFilter(e.target.value)}><option value="">All statuses</option><option value="OPEN">Open</option><option value="IN_PROGRESS">In progress</option><option value="RESOLVED">Resolved</option><option value="CLOSED">Closed</option></select></div>{tickets.length === 0 ? <Empty>No tickets match this filter.</Empty> : tickets.map((ticket) => <article className="admin-card" key={ticket.id}><div className="admin-card-head"><div><span className="tag tag-upcoming">{ticket.status_display}</span><h3>#{ticket.id} {ticket.subject}</h3><small>Reported by {ticket.reporter_username || 'deleted user'} · {new Date(ticket.created_at).toLocaleString()}</small></div><div className="admin-actions">{ticket.status === 'OPEN' && <button className="btn btn-outline btn-sm" onClick={() => updateTicket(ticket, 'IN_PROGRESS')}>Start work</button>}{!['RESOLVED', 'CLOSED'].includes(ticket.status) && <button className="btn btn-primary btn-sm" onClick={() => updateTicket(ticket, 'RESOLVED')}>Resolve</button>}{ticket.status === 'RESOLVED' && <button className="btn btn-outline btn-sm" onClick={() => updateTicket(ticket, 'CLOSED')}>Close</button>}</div></div><div className="support-thread">{(ticket.messages || []).map((message) => { const fromUser = message.author_username === ticket.reporter_username; return <div className={`support-message ${fromUser ? 'from-user' : 'from-admin'}`} key={message.id}><div><strong>{fromUser ? ticket.reporter_username : 'Support team'}</strong><time>{new Date(message.created_at).toLocaleString()}</time></div><p>{message.message}</p></div> })}</div>{!['RESOLVED', 'CLOSED'].includes(ticket.status) && <form className="admin-ticket-reply" onSubmit={(event) => replyToTicket(event, ticket)}><input className="input" aria-label={`Reply to ticket ${ticket.id}`} placeholder="Write a reply to the user" value={ticketReplies[ticket.id] || ''} onChange={(event) => setTicketReplies((old) => ({ ...old, [ticket.id]: event.target.value }))} required/><button className="btn btn-outline btn-sm" disabled={busy === `ticket-${ticket.id}`}>Send reply</button></form>}</article>)}</div>}

      {section === 'categories' && <div className="admin-section"><h2>Product categories</h2><p>Categories are available to sellers when they create auction products.</p><form className="admin-category-form" onSubmit={createCategory}><input className="input" placeholder="New category name" value={categoryName} onChange={(e) => setCategoryName(e.target.value)} required/><button className="btn btn-primary" disabled={busy === 'category-new'}>Add category</button></form>{categories.map((category) => <div className="list-row" key={category.id}><div className="flex1"><strong>{category.name}</strong></div><button className="btn btn-outline btn-sm" onClick={() => renameCategory(category)}>Rename</button><button className="btn btn-outline btn-sm" onClick={() => removeCategory(category)}>Delete</button></div>)}</div>}
    </>}
  </section></Layout>
}
