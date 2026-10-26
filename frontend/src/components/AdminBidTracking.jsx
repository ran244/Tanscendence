import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { get } from '../api/client'
import { formatMoney } from '../utils/money'

const PAGE_SIZE = 25
const REFRESH_INTERVAL_MS = 10000
const EMPTY_PAGE = {
  count: 0,
  page: 1,
  total_pages: 1,
  next: null,
  previous: null,
  results: [],
}
const exactTime = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  timeZoneName: 'short',
})

function formatBidTime(value) {
  const timestamp = new Date(value)
  return Number.isNaN(timestamp.getTime()) ? 'Unknown time' : exactTime.format(timestamp)
}

function apiPathFromLink(link) {
  const url = new URL(link, window.location.origin)
  return `${url.pathname.replace(/^\/api/, '')}${url.search}`
}

async function fetchAllActiveEvents() {
  const events = []
  let path = '/auctions/admin/events/?status=ACTIVE&page_size=100'
  while (path) {
    const page = await get(path)
    events.push(...(page.results || []))
    path = page.next ? apiPathFromLink(page.next) : ''
  }
  return events
}

export default function AdminBidTracking() {
  const [activeEvents, setActiveEvents] = useState([])
  const [bidPage, setBidPage] = useState(EMPTY_PAGE)
  const [statusFilter, setStatusFilter] = useState('ACCEPTED')
  const [eventFilter, setEventFilter] = useState('')
  const [lotFilter, setLotFilter] = useState('')
  const [pageNumber, setPageNumber] = useState(1)
  const [loadingEvents, setLoadingEvents] = useState(true)
  const [loadingBids, setLoadingBids] = useState(true)
  const [eventsError, setEventsError] = useState('')
  const [bidsError, setBidsError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const latestBidRequest = useRef(0)

  const loadEvents = useCallback(async () => {
    setLoadingEvents(true)
    try {
      setActiveEvents(await fetchAllActiveEvents())
      setEventsError('')
    } catch (requestError) {
      setEventsError(requestError.message)
    } finally {
      setLoadingEvents(false)
    }
  }, [])

  const loadBids = useCallback(async ({ quiet = false } = {}) => {
    const requestId = ++latestBidRequest.current
    if (!quiet) setLoadingBids(true)
    try {
      const params = new URLSearchParams({
        page: String(pageNumber),
        page_size: String(PAGE_SIZE),
      })
      if (statusFilter !== 'ALL') params.set('status', statusFilter)
      if (eventFilter) params.set('event', eventFilter)
      if (lotFilter) params.set('lot', lotFilter)
      const nextPage = await get(`/auctions/admin/bids/?${params.toString()}`)
      if (requestId !== latestBidRequest.current) return
      setBidPage(nextPage)
      setBidsError('')
      setLastUpdated(new Date())
    } catch (requestError) {
      if (requestId === latestBidRequest.current) setBidsError(requestError.message)
    } finally {
      if (requestId === latestBidRequest.current) setLoadingBids(false)
    }
  }, [eventFilter, lotFilter, pageNumber, statusFilter])

  useEffect(() => { loadEvents() }, [loadEvents])
  useEffect(() => { loadBids() }, [loadBids])
  useEffect(() => {
    if (pageNumber !== 1) return undefined
    const refreshVisiblePage = () => {
      if (document.visibilityState === 'visible') loadBids({ quiet: true })
    }
    const interval = window.setInterval(refreshVisiblePage, REFRESH_INTERVAL_MS)
    document.addEventListener('visibilitychange', refreshVisiblePage)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', refreshVisiblePage)
    }
  }, [loadBids, pageNumber])

  const availableLots = useMemo(() => {
    const events = eventFilter
      ? activeEvents.filter((event) => String(event.id) === eventFilter)
      : activeEvents
    return events.flatMap((event) => (event.lots || []).map((lot) => ({
      ...lot,
      eventTitle: event.title,
    })))
  }, [activeEvents, eventFilter])

  const changeStatus = (value) => {
    setStatusFilter(value)
    setPageNumber(1)
  }
  const changeEvent = (value) => {
    setEventFilter(value)
    setLotFilter('')
    setPageNumber(1)
  }
  const changeLot = (value) => {
    setLotFilter(value)
    setPageNumber(1)
  }
  const refreshAll = () => {
    loadEvents()
    loadBids()
  }

  const rows = bidPage.results || []
  const initialLoading = (loadingEvents || loadingBids) && !lastUpdated

  return (
    <div className="admin-section">
      <div className="admin-section-head">
        <div>
          <h2>Live bid tracking</h2>
          <p>Server-recorded bids for active auctions. Accepted bids and rejected attempts remain clearly identified.</p>
        </div>
        <button className="btn btn-outline btn-sm" type="button" onClick={refreshAll} disabled={loadingEvents || loadingBids}>
          {loadingEvents || loadingBids ? 'Refreshing…' : 'Refresh bids'}
        </button>
      </div>

      <div className="admin-bid-filters">
        <label>
          Result
          <select className="input" value={statusFilter} onChange={(event) => changeStatus(event.target.value)}>
            <option value="ACCEPTED">Accepted bids</option>
            <option value="REJECTED">Rejected attempts</option>
            <option value="ALL">All records</option>
          </select>
        </label>
        <label>
          Auction
          <select className="input" value={eventFilter} onChange={(event) => changeEvent(event.target.value)}>
            <option value="">All active auctions</option>
            {activeEvents.map((event) => <option key={event.id} value={event.id}>{event.title}</option>)}
          </select>
        </label>
        <label>
          Lot
          <select className="input" value={lotFilter} onChange={(event) => changeLot(event.target.value)}>
            <option value="">All lots</option>
            {availableLots.map((lot) => <option key={lot.id} value={lot.id}>{lot.eventTitle} — Lot {lot.lot_number}: {lot.product_name}</option>)}
          </select>
        </label>
      </div>

      {(eventsError || bidsError) && <p className="form-error" role="alert">{eventsError || bidsError}</p>}
      <div className="admin-bid-status" aria-live="polite">
        <span>{bidPage.count} matching record{bidPage.count === 1 ? '' : 's'}</span>
        {lastUpdated && <span>Updated {formatBidTime(lastUpdated)}</span>}
      </div>

      {initialLoading ? (
        <div className="empty-state"><p>Loading active bid records…</p></div>
      ) : activeEvents.length === 0 && rows.length === 0 && !eventsError ? (
        <div className="empty-state"><p>No auctions are active right now.</p></div>
      ) : rows.length === 0 ? (
        <div className="empty-state"><p>No bid records match this selection.</p></div>
      ) : (
        <div className="admin-bid-table-wrap">
          <table className="admin-bid-table">
            <thead>
              <tr>
                <th scope="col">Auction and lot</th>
                <th scope="col">Bidder</th>
                <th scope="col">Amount</th>
                <th scope="col">Result</th>
                <th scope="col">Placed at</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((bid) => {
                const invalidInput = bid.status === 'REJECTED' && bid.rejection_reason === 'INVALID_AMOUNT'
                return (
                  <tr key={bid.id} className={bid.status === 'REJECTED' ? 'rejected' : ''}>
                    <td><strong>{bid.event_title}</strong><small>Lot {bid.lot_number}: {bid.product_name} · #{bid.lot_id}</small></td>
                    <td><strong>{bid.bidder_username}</strong><small>{bid.bidder_id ? `User #${bid.bidder_id}` : 'Account deleted'}</small></td>
                    <td className={invalidInput ? 'invalid-amount' : ''}>{invalidInput ? 'Invalid input' : formatMoney(bid.amount)}</td>
                    <td>
                      <span className={`tag ${bid.status === 'ACCEPTED' ? 'tag-live' : 'tag-lost'}`}>{bid.status_display}</span>
                      {bid.is_highest && <small className="current-highest">Current highest</small>}
                      {bid.rejection_reason_display && <small>{bid.rejection_reason_display}</small>}
                    </td>
                    <td><time dateTime={bid.created_at} title={bid.created_at}>{formatBidTime(bid.created_at)}</time><small>Bid #{bid.id}</small></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {bidPage.total_pages > 1 && (
        <nav className="admin-pagination" aria-label="Bid tracking pages">
          <button className="btn btn-outline btn-sm" type="button" disabled={!bidPage.previous || loadingBids} onClick={() => setPageNumber((page) => Math.max(1, page - 1))}>Previous</button>
          <span>Page {bidPage.page} of {bidPage.total_pages}</span>
          <button className="btn btn-outline btn-sm" type="button" disabled={!bidPage.next || loadingBids} onClick={() => setPageNumber((page) => page + 1)}>Next</button>
        </nav>
      )}
    </div>
  )
}
