import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from './Icons'
import AuctionCard from './AuctionCard'

const AUTOPLAY_INTERVAL = 3200

export default function AuctionCarousel({ lots, onOpen }) {
  const trackRef = useRef(null)
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)

  const cardStep = () => {
    const track = trackRef.current
    return track?.firstChild ? track.firstChild.offsetWidth + 22 : 320
  }

  const goTo = (i) => {
    const track = trackRef.current
    if (!track || lots.length === 0) return
    const next = ((i % lots.length) + lots.length) % lots.length
    track.scrollTo({ left: next * cardStep(), behavior: 'smooth' })
    setIndex(next)
  }

  const scrollByCards = (dir) => goTo(index + dir)

  // Moving-ribbon autoplay: advances to the next card on its own, and
  // pauses the instant the pointer is over the strip so people can read
  // a card (or its hover overlay) without it sliding away.
  useEffect(() => {
    if (paused || lots.length <= 1) return
    const id = setInterval(() => {
      setIndex((i) => {
        const next = (i + 1) % lots.length
        const track = trackRef.current
        track?.scrollTo({ left: next * cardStep(), behavior: 'smooth' })
        return next
      })
    }, AUTOPLAY_INTERVAL)
    return () => clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused, lots.length])

  if (lots.length === 0) {
    return (
      <div className="empty-state">
        <h3>No live auctions right now</h3>
        <p>Check back soon, or take a look at what&rsquo;s coming up below.</p>
      </div>
    )
  }

  return (
    <div>
      <div
        className="carousel"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        <button className="carousel-arrow" onClick={() => scrollByCards(-1)} aria-label="Previous auctions">
          <ChevronLeft />
        </button>
        <div className="carousel-track" ref={trackRef}>
          {lots.map((lot) => (
            <AuctionCard key={lot.id} lot={lot} onOpen={onOpen} />
          ))}
        </div>
        <button className="carousel-arrow" onClick={() => scrollByCards(1)} aria-label="Next auctions">
          <ChevronRight />
        </button>
      </div>
      <div className="dots">
        {lots.map((lot, i) => (
          <button
            key={lot.id}
            className={`dot ${i === index ? 'active' : ''}`}
            onClick={() => goTo(i)}
            aria-label={`Go to ${lot.product.name}`}
          />
        ))}
      </div>
    </div>
  )
}
