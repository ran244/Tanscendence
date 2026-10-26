import { useEffect, useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import AuctionModal from '../components/AuctionModal'
import AuctionCard from '../components/AuctionCard'
import { ChevronLeft, ChevronRight } from '../components/Icons'
import { useAuth } from '../context/AuthContext'
import { useData } from '../context/DataContext'

const countdown = (target, now) => {
  const seconds = Math.max(0, Math.floor((new Date(target).getTime() - now) / 1000))
  const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60); const secs = seconds % 60
  return `${days ? `${days}d ` : ''}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function EventRibbon({ title, events, mode, now, onOpen }) {
  const [index, setIndex] = useState(0)
  const [visibleCount, setVisibleCount] = useState(() => {
    if (window.matchMedia('(max-width: 640px)').matches) return 1
    if (window.matchMedia('(max-width: 860px)').matches) return 2
    return 3
  })
  useEffect(() => { if (index >= events.length) setIndex(0) }, [events.length, index])

  useEffect(() => {
    const updateVisibleCount = () => {
      if (window.matchMedia('(max-width: 640px)').matches) setVisibleCount(1)
      else if (window.matchMedia('(max-width: 860px)').matches) setVisibleCount(2)
      else setVisibleCount(3)
    }
    window.addEventListener('resize', updateVisibleCount)
    return () => window.removeEventListener('resize', updateVisibleCount)
  }, [])

  useEffect(() => {
    if (events.length <= 3) return
    const interval = setInterval(() => {
      setIndex((old) => (old + 1) % events.length)
    }, 5000)
    return () => clearInterval(interval)
  }, [events.length])

  const move = (direction) => setIndex((old) => events.length ? (old + direction + events.length) % events.length : 0)
  const canNavigate = events.length > visibleCount
  const visibleEvents = events.slice(0, Math.min(visibleCount, events.length)).map((_, offset) => events[(index + offset) % events.length])

  return <section className="event-ribbon-section">
    <div className="event-ribbon-heading"><h2>{title}</h2><span>{events.length} event{events.length === 1 ? '' : 's'}</span></div>
    {!events.length ? <div className="empty-state"><p>No {mode.toLowerCase()} auctions right now.</p></div> : <div className="event-carousel-shell">
      {canNavigate && (
        <button className="carousel-arrow carousel-arrow-left" onClick={() => move(-1)} aria-label={`Previous ${mode.toLowerCase()} auction`}><ChevronLeft /></button>
      )}
      <div className="event-ribbon">
        {visibleEvents.map((event, offset) => {
          const highestBid = Math.max(...event.lots.map((lot) => Number(lot.current_price) || 0), 0)
          return <button
            key={`${event.id}-${offset}`}
            className="event-showcase"
            onClick={() => onOpen(event)}
            aria-label={`Open ${event.title}`}
          >
            <img src={event.lots[0]?.product.image || '/placeholder.svg'} alt="" />
            <span className={`tag ${mode === 'LIVE' ? 'tag-live' : 'tag-upcoming'}`}>{mode}</span>
            <span className="event-countdown"><small>{mode === 'LIVE' ? 'Ends in' : 'Starts in'}</small><strong>{countdown(mode === 'LIVE' ? event.end_time : event.start_time, now)}</strong></span>
            <div className="event-hover-overlay">
              <strong>{mode === 'LIVE' ? `Highest bid: $${highestBid.toFixed(2)}` : `${event.lots.length} lot${event.lots.length === 1 ? '' : 's'}`}</strong>
              <small>{mode === 'LIVE' ? `${event.lots.length} lot${event.lots.length === 1 ? '' : 's'} in this event` : 'Click to view lot details'}</small>
            </div>
            <span className="event-showcase-copy">
              <strong>{event.title}</strong>
              <small>{event.lots.length} lot{event.lots.length === 1 ? '' : 's'} · {mode === 'LIVE' ? `Highest bid: $${highestBid.toFixed(2)}` : 'Click to view lots & details'}</small>
            </span>
          </button>
        })}
      </div>
      {canNavigate && (
        <button className="carousel-arrow carousel-arrow-right" onClick={() => move(1)} aria-label={`Next ${mode.toLowerCase()} auction`}><ChevronRight /></button>
      )}
      {canNavigate && <div className="event-carousel-dots" aria-label={`${title} carousel position`}>
        {events.map((event, dotIndex) => <button key={event.id} className={dotIndex === index ? 'active' : ''} onClick={() => setIndex(dotIndex)} aria-label={`Show ${event.title}`} aria-current={dotIndex === index ? 'true' : undefined} />)}
      </div>}
    </div>}
  </section>
}

function SelectedEventViewer({ selectedEvent, onClose, onOpenLot }) {
  const [lotIndex, setLotIndex] = useState(0)
  const [visibleCount, setVisibleCount] = useState(() => {
    if (window.matchMedia('(max-width: 640px)').matches) return 1
    if (window.matchMedia('(max-width: 860px)').matches) return 2
    return 3
  })
  const lots = selectedEvent?.lots || []

  useEffect(() => {
    const updateVisibleCount = () => {
      if (window.matchMedia('(max-width: 640px)').matches) setVisibleCount(1)
      else if (window.matchMedia('(max-width: 860px)').matches) setVisibleCount(2)
      else setVisibleCount(3)
    }
    window.addEventListener('resize', updateVisibleCount)
    return () => window.removeEventListener('resize', updateVisibleCount)
  }, [])

  useEffect(() => { if (lotIndex >= lots.length) setLotIndex(0) }, [lotIndex, lots.length])

  const moveLot = (dir) => setLotIndex((prev) => (prev + dir + lots.length) % lots.length)
  const canNavigate = lots.length > visibleCount
  const visibleLots = lots.slice(0, Math.min(visibleCount, lots.length)).map((_, offset) => lots[(lotIndex + offset) % lots.length])

  return (
    <section className="selected-event panel">
      <div className="selected-event-header">
        <div>
          <span className="eyebrow">Auction event</span>
          <h2>{selectedEvent.title}</h2>
          <p>{selectedEvent.description}</p>
        </div>
        <button className="close-x-btn" onClick={onClose} aria-label="Close lots" title="Close">✕</button>
      </div>

      <div className="selected-event-lots-container">
        {canNavigate && (
          <button className="carousel-arrow" onClick={() => moveLot(-1)} aria-label="Previous lot"><ChevronLeft /></button>
        )}
        <div className="selected-event-lots-wrapper">
          {visibleLots.map((lot) => <div key={lot.id} className="single-lot-item"><AuctionCard lot={lot} onOpen={onOpenLot} /></div>)}
        </div>
        {canNavigate && (
          <button className="carousel-arrow" onClick={() => moveLot(1)} aria-label="Next lot"><ChevronRight /></button>
        )}
      </div>
      {canNavigate && (
        <div className="lot-carousel-dots" aria-label={`${selectedEvent.title} lot carousel position`}>
          {lots.map((lot, dotIndex) => (
            <button
              key={lot.id}
              className={dotIndex === lotIndex ? 'active' : ''}
              onClick={() => setLotIndex(dotIndex)}
              aria-label={`Show lot ${lot.lot_number}`}
              aria-current={dotIndex === lotIndex ? 'true' : undefined}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default function Home() {
  const [activeLot, setActiveLot] = useState(null); const [selectedEvent, setSelectedEvent] = useState(null); const [now, setNow] = useState(Date.now())
  const { user, refreshUser, loading } = useAuth(); const { events } = useData(); const navigate = useNavigate()
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  const live = useMemo(() => events.filter((event) => new Date(event.start_time).getTime() <= now && new Date(event.end_time).getTime() > now), [events, now])
  const upcoming = useMemo(() => events.filter((event) => new Date(event.start_time).getTime() > now), [events, now])
  useEffect(() => {
    if (!selectedEvent) return
    const current = events.find((event) => event.id === selectedEvent.id)
    if (current && current !== selectedEvent) setSelectedEvent(current)
  }, [events, selectedEvent])
  const selectedIsLive = selectedEvent && live.some((event) => event.id === selectedEvent.id)
  if (!loading && user?.role === 'ADMIN') return <Navigate to="/admin" replace />
  const createAuction = async () => { if (!user) return navigate('/login'); const current = await refreshUser(); navigate(current?.role === 'ADMIN' ? '/admin' : '/create-auction') }
  return <Layout><section className="hero-section">
    <div className="event-ribbons">
      <EventRibbon title="Live auctions" events={live} mode="LIVE" now={now} onOpen={setSelectedEvent} />
      {selectedIsLive && <SelectedEventViewer selectedEvent={selectedEvent} onClose={() => setSelectedEvent(null)} onOpenLot={setActiveLot} />}
      {user?.role !== 'ADMIN' && <div className="cta-banner"><div><h3>Have something worth discovering?</h3><p style={{ margin: 0 }}>Create an event, add its lots, then submit it when you are ready.</p></div><button className="btn btn-tan" onClick={createAuction}>Start an auction</button></div>}
      <EventRibbon title="Upcoming auctions" events={upcoming} mode="UPCOMING" now={now} onOpen={setSelectedEvent} />
      {selectedEvent && !selectedIsLive && <SelectedEventViewer selectedEvent={selectedEvent} onClose={() => setSelectedEvent(null)} onOpenLot={setActiveLot} />}
    </div>
  </section>{activeLot && <AuctionModal lot={activeLot} onClose={() => setActiveLot(null)} />}</Layout>
}
