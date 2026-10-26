import { useEffect, useState } from 'react'
import { formatMoney } from '../utils/money'
import { useNavigate } from 'react-router-dom'
import { CloseIcon } from './Icons'
import { useAuth } from '../context/AuthContext'
import { useData } from '../context/DataContext'
import { getLiveStatus, formatCountdown, formatTimeUntilStart, statusTagMeta } from '../utils/auctionStatus'
import { get } from '../api/client'

export default function AuctionModal({ lot, onClose }) {
  const { user, refreshUser } = useAuth()
  const { isSaved, toggleSaved, placeBid } = useData()
  const navigate = useNavigate()
  const [bidValue, setBidValue] = useState('')
  const [placed, setPlaced] = useState(false)
  const [error, setError] = useState('')
  const [, forceTick] = useState(0)
  const [detail, setDetail] = useState(lot)
  const [detailsLoaded, setDetailsLoaded] = useState(false)

  const status = getLiveStatus(lot)
  const tag = statusTagMeta[status]
  const saved = isSaved(lot.id)

  useEffect(() => {
    if (status !== 'ACTIVE') return
    const id = setInterval(() => forceTick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [status])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    setDetailsLoaded(false)
    get(`/auctions/lots/${lot.id}/`)
      .then((data) => setDetail({
        ...lot,
        description: data.description,
        category: data.category,
        seller: data.seller,
        winner_username: data.winner_username,
        product: {
          ...lot.product,
          description: data.description,
          category: data.category?.name || lot.product.category,
          owner: data.seller?.username,
        },
        minimum_next_bid: Number(data.minimum_next_bid),
        minimum_increment: Number(data.minimum_increment),
      }))
      .catch(() => {})
      .finally(() => setDetailsLoaded(true))
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/lot/${lot.id}/`)
    socket.onmessage = (event) => { const message = JSON.parse(event.data); if (['snapshot', 'bid.accepted'].includes(message.type)) setDetail((old) => ({ ...old, current_price: Number(message.current_price), minimum_next_bid: Number(message.minimum_next_bid), bid_count: message.bid_count })) }
    return () => socket.close()
  }, [lot])

  const minBid = detail.minimum_next_bid || detail.current_price + detail.minimum_increment
  const isOwner = Boolean(user && (
    detail.seller?.id === user.id || detail.product?.owner === user.username
  ))

  const handleBid = async (e) => {
    e.preventDefault()
    if (!user) {
      onClose()
      navigate('/login')
      return
    }
    const current = await refreshUser()
    if (current?.role === 'ADMIN') {
      setError('Administrator accounts cannot place bids.')
      return
    }
    if (isOwner) {
      setError('You cannot bid on your own auction lot.')
      return
    }
    try {
      const result = await placeBid(lot.id, bidValue)
      setDetail((old) => ({ ...old, current_price: Number(result.current_price), minimum_next_bid: Number(result.minimum_next_bid), bid_count: result.bid_count }))
      setPlaced(true)
    } catch (err) { setError(err.message) }
  }

  const handleSave = () => {
    if (!user) {
      onClose()
      navigate('/login')
      return
    }
    toggleSaved(lot.id).catch(() => {})
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-img-wrap">
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
          <img className="modal-img" src={lot.product.image} alt={lot.product.name} />
        </div>
        <div className="modal-body">
          <span className={`tag ${tag.cls}`}>{tag.label}</span>
          <h2 style={{ marginTop: 12 }}>{lot.product.name}</h2>
          <p>{detail.product.description}</p>

          <div className="modal-meta-row">
            <span>Category: <strong>{detail.product.category}</strong></span>
            <span>Lot #{lot.lot_number}</span>
            <span>{detail.bid_count} bids placed on this lot</span>
          </div>

          <div className="bid-box">
            {status === 'UPCOMING' ? (
              <>
                <div className="current">Starts at {formatMoney(lot.starting_price)}</div>
                <p style={{ margin: '4px 0 0' }}>
                  Bidding opens {formatTimeUntilStart(lot.start_time)} ({new Date(lot.start_time).toLocaleString()}).
                </p>
              </>
            ) : status === 'ENDED' ? (
              <>
                <div className="current">{detail.winner_username ? `Winning price ${formatMoney(detail.current_price)}` : 'No winning bid'}</div>
                <p style={{ margin: '4px 0 0' }}>
                  This auction has ended.{detail.winner_username ? ` Winner: ${detail.winner_username}.` : ''}
                </p>
              </>
            ) : (
              <>
                <div className="current">{formatMoney(detail.current_price)} <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-soft)' }}>current bid</span></div>
                <p style={{ margin: '4px 0 0' }}>
                  Time left: <span className="countdown">{formatCountdown(lot.end_time)}</span>
                </p>

                {!detailsLoaded ? (
                  <p style={{ marginTop: 14 }}>Checking bidding eligibility…</p>
                ) : user?.role === 'ADMIN' ? (
                  <p style={{ marginTop: 14 }}>Administrators can review auctions, but cannot place bids.</p>
                ) : isOwner ? (
                  <p style={{ marginTop: 14 }}>This is your auction lot. Sellers cannot bid on their own items.</p>
                ) : placed ? (
                  <p style={{ marginTop: 14, fontWeight: 600, color: 'var(--success)' }}>
                    Your bid of {formatMoney(bidValue)} has been placed.
                  </p>
                ) : (
                  <>
                  {error && <p role="alert" className="form-error">{error}</p>}
                  <form className="bid-row" onSubmit={handleBid}>
                    <input
                      className="input"
                      type="number"
                      min={minBid}
                      step="1"
                      placeholder={`${formatMoney(minBid)} or more`}
                      value={bidValue}
                      onChange={(e) => setBidValue(e.target.value)}
                      required
                    />
                    <button className="btn btn-primary" type="submit">
                      Place bid
                    </button>
                  </form>
                  </>
                )}
                {!user && (
                  <p style={{ marginTop: 10, fontSize: 12.5 }}>
                    You&rsquo;ll need to log in to place a bid.
                  </p>
                )}
              </>
            )}

            <button
              type="button"
              className={`btn btn-sm ${saved ? 'btn-tan' : 'btn-outline'}`}
              onClick={handleSave}
              style={{ marginTop: 16 }}
            >
              {saved ? '\u2605 Saved' : '\u2606 Save for later'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
