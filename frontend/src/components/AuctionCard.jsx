import { useEffect, useState } from 'react'
import { formatMoney } from '../utils/money'
import { getLiveStatus, formatCountdown, formatTimeUntilStart, statusTagMeta } from '../utils/auctionStatus'
import { useData } from '../context/DataContext'

export default function AuctionCard({ lot, onOpen }) {
  const { isSaved, toggleSaved } = useData()
  const [hovering, setHovering] = useState(false)
  const [, forceTick] = useState(0)

  const status = getLiveStatus(lot)
  const tag = statusTagMeta[status]
  const saved = isSaved(lot.id)

  // Only tick the clock while the card is actually hovered, so we don't
  // run a timer for every card on the page.
  useEffect(() => {
    if (!hovering || status !== 'ACTIVE') return
    const id = setInterval(() => forceTick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [hovering, status])

  return (
    <div
      className="auction-card"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <button
        className="auction-card-clickable"
        onClick={() => onOpen(lot)}
        aria-label={`View ${lot.product.name}`}
      >
        <div className="thumb-wrap">
          <img className="thumb" src={lot.product.image} alt={lot.product.name} loading="lazy" />
          {/* the status tag stays on top even while hovering */}
          <span className={`tag card-tag ${tag.cls}`}>{tag.label}</span>

          {hovering && status !== 'UPCOMING' && (
            <div className="hover-overlay">
              {status === 'ACTIVE' ? (
                <>
                  <span className="hover-line">Time left: {formatCountdown(lot.end_time)}</span>
                  <span className="hover-line strong">Current bid: {formatMoney(lot.current_price)}</span>
                </>
              ) : (
                <span className="hover-line strong">Sold for {formatMoney(lot.current_price)}</span>
              )}
            </div>
          )}
          {hovering && status === 'UPCOMING' && (
            <div className="hover-overlay">
              <span className="hover-line">Opens {formatTimeUntilStart(lot.start_time)}</span>
              <span className="hover-line strong">Starting bid: {formatMoney(lot.starting_price)}</span>
            </div>
          )}
        </div>
        <div className="info">
          <h3>{lot.product.name}</h3>
          <div className="meta">
            <span>{lot.bid_count} bids</span>
            <span className="price">{formatMoney(lot.current_price)}</span>
          </div>
        </div>
      </button>
      <button
        className={`save-btn ${saved ? 'saved' : ''}`}
        onClick={(e) => {
          e.stopPropagation()
          toggleSaved(lot.id).catch(() => {})
        }}
        aria-pressed={saved}
        aria-label={saved ? 'Remove from saved items' : 'Save this auction'}
        title={saved ? 'Saved' : 'Save'}
      >
        {saved ? '\u2605' : '\u2606'}
      </button>
    </div>
  )
}
