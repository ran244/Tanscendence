import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { CloseIcon } from '../components/Icons'
import { del, get, post } from '../api/client'
import { formatMoney } from '../utils/money'

const reviewedCancellationStatuses = ['APPROVED', 'SCHEDULED']
const statusClasses = {
  APPROVED: 'tag-approved', SCHEDULED: 'tag-approved', ACTIVE: 'tag-live',
  REJECTED: 'tag-rejected', CANCELLED: 'tag-cancelled',
  PENDING_APPROVAL: 'tag-pending', DRAFT: 'tag-pending', ENDED: 'tag-ended',
}

function EventDetailsModal({ event, onClose }) {
  useEffect(() => {
    const closeOnEscape = (keyboardEvent) => keyboardEvent.key === 'Escape' && onClose()
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [onClose])

  return <div className="modal-backdrop" onClick={onClose}>
    <article className="modal owner-event-modal" role="dialog" aria-modal="true" aria-labelledby={`event-title-${event.id}`} onClick={(clickEvent) => clickEvent.stopPropagation()}>
      <button className="modal-close" onClick={onClose} aria-label="Close auction details"><CloseIcon /></button>
      <div className="modal-body">
        <span className={`tag owner-status-tag ${statusClasses[event.status] || 'tag-ended'}`}>{event.status_display}</span>
        <h2 id={`event-title-${event.id}`}>{event.title}</h2>
        <p>{event.description || 'No auction description was provided.'}</p>
        <div className="owner-event-meta">
          <div><small>Starts</small><strong>{new Date(event.start_time).toLocaleString()}</strong></div>
          <div><small>Ends</small><strong>{new Date(event.end_time).toLocaleString()}</strong></div>
          <div><small>Lots</small><strong>{event.lots.length}</strong></div>
          {event.revision_number > 0 && <div><small>Revision</small><strong>#{event.revision_number}</strong></div>}
        </div>
        {event.rejection_reason && <div className="owner-event-message rejected"><strong>Rejection reason</strong><p>{event.rejection_reason}</p></div>}
        {event.cancellation_request && <div className="owner-event-message"><strong>Cancellation request: {event.cancellation_request.status_display || event.cancellation_request.status}</strong><p>{event.cancellation_request.reason}</p></div>}
        <h3 className="owner-lots-heading">Auction lots</h3>
        <div className="owner-event-lots">
          {event.lots.map((lot) => <section className="owner-lot-card" key={lot.id}>
            <img src={lot.product_image || '/placeholder.svg'} alt="" />
            <div>
              <span className="tag tag-ended">{lot.status?.replaceAll('_', ' ')}</span>
              <h4>Lot {lot.lot_number}: {lot.product_name}</h4>
              <dl>
                <div><dt>Starting price</dt><dd>{formatMoney(lot.starting_price)}</dd></div>
                <div><dt>Current price</dt><dd>{formatMoney(lot.current_price)}</dd></div>
                <div><dt>Minimum increment</dt><dd>{formatMoney(lot.minimum_increment)}</dd></div>
                <div><dt>Bids</dt><dd>{lot.bid_count}</dd></div>
              </dl>
            </div>
          </section>)}
        </div>
      </div>
    </article>
  </div>
}

export default function MyAuctions() {
  const [events, setEvents] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(null)
  const [selectedEvent, setSelectedEvent] = useState(null)
  const navigate = useNavigate()
  const load = () => get('/auctions/events/?page_size=100').then((data) => setEvents(data.results || [])).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])

  const cancelDirectly = async (event) => {
    setBusy(event.id); setError(''); setNotice('')
    try {
      await post(`/auctions/events/${event.id}/cancel/`, { reason: 'Cancelled by organizer before approval' })
      setNotice(`“${event.title}” was cancelled.`); await load()
    } catch (err) { setError(err.message) } finally { setBusy(null) }
  }

  const deleteDraft = async (event) => {
    if (!window.confirm(`Delete the private draft “${event.title}”?`)) return
    setBusy(event.id); setError(''); setNotice('')
    try { await del(`/auctions/events/${event.id}/`); setNotice(`Draft “${event.title}” was deleted.`); await load() }
    catch (err) { setError(err.message) } finally { setBusy(null) }
  }

  const requestCancellation = async (event) => {
    const reason = window.prompt(`Why do you want to cancel “${event.title}”?`)?.trim()
    if (!reason) return
    setBusy(event.id); setError(''); setNotice('')
    try {
      await post(`/auctions/events/${event.id}/cancellation-request/`, { reason })
      setNotice(`Cancellation of “${event.title}” was sent to an administrator for review.`); await load()
    } catch (err) { setError(err.message) } finally { setBusy(null) }
  }

  const editEvent = async (event) => {
    setBusy(event.id); setError(''); setNotice('')
    try {
      if (['APPROVED', 'SCHEDULED'].includes(event.status)) {
        const revision = await post(`/auctions/events/${event.id}/revise/`)
        navigate(`/auctions/${revision.id}/edit`)
      } else navigate(`/auctions/${event.id}/edit`)
    } catch (err) { setError(err.message); setBusy(null) }
  }

  return <Layout><section className="my-auctions-page">
    <div className="my-auctions-heading"><h2>My auctions</h2><Link className="btn btn-tan" to="/create-auction">+ New auction</Link></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="admin-notice" role="status">{notice}</p>}
    {events.length === 0 ? <div className="empty-state"><h3>No auctions yet</h3></div> : events.map((event) => {
      const cancellation = event.cancellation_request
      const beforeDeadline = Date.now() <= new Date(event.cancellation_deadline).getTime()
      const needsReview = reviewedCancellationStatuses.includes(event.status)
      const openDetails = () => setSelectedEvent(event)
      return <article key={event.id} className="list-row auction-owner-row" role="button" tabIndex="0" aria-label={`View details for ${event.title}`} onClick={openDetails} onKeyDown={(keyboardEvent) => { if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') { keyboardEvent.preventDefault(); openDetails() } }}>
        <div className="flex1">
          <h4>{event.title}</h4>
          <div className="sub">{event.lots.length} lot(s) · {new Date(event.start_time).toLocaleString()}</div>
          {event.rejection_reason && <div className="form-error">{event.rejection_reason}</div>}
          {cancellation?.status === 'PENDING' && <div className="cancellation-record"><strong>Cancellation awaiting administrator review</strong><span>Your reason: {cancellation.reason}</span></div>}
          {cancellation?.status === 'REJECTED' && <div className="cancellation-record rejected"><strong>Cancellation request rejected</strong><span>{cancellation.review_reason}</span></div>}
          {cancellation?.status === 'APPROVED' && <div className="cancellation-record approved"><strong>Cancellation approved</strong></div>}
          {needsReview && !beforeDeadline && cancellation?.status !== 'PENDING' && <small className="sub">The 24-hour cancellation request window has closed.</small>}
        </div>
        <div className="owner-auction-controls" onClick={(clickEvent) => clickEvent.stopPropagation()}>
          <span className={`tag owner-status-tag ${statusClasses[event.status] || 'tag-ended'}`}>{event.status_display}</span>
          <div className="owner-auction-actions">
            {event.status !== 'REJECTED' && beforeDeadline && ['DRAFT', 'APPROVED', 'SCHEDULED'].includes(event.status) && <button className="btn btn-outline btn-sm" disabled={busy === event.id} onClick={() => editEvent(event)}>Edit</button>}
            {event.status === 'DRAFT' && <button className="btn btn-ghost btn-sm" disabled={busy === event.id} onClick={() => deleteDraft(event)}>Delete</button>}
            {event.status === 'PENDING_APPROVAL' && <button className="btn btn-ghost btn-sm" disabled={busy === event.id} onClick={() => cancelDirectly(event)}>Cancel</button>}
            {needsReview && beforeDeadline && cancellation?.status !== 'PENDING' && <button className="btn btn-outline btn-sm" disabled={busy === event.id} onClick={() => requestCancellation(event)}>Cancel</button>}
          </div>
        </div>
      </article>
    })}
    {selectedEvent && <EventDetailsModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />}
  </section></Layout>
}
