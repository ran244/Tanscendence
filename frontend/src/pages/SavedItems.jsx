import { useState } from 'react'
import Layout from '../components/Layout'
import AuctionCard from '../components/AuctionCard'
import AuctionModal from '../components/AuctionModal'
import { useData } from '../context/DataContext'

export default function SavedItems() {
  const { savedLots } = useData()
  const [activeLot, setActiveLot] = useState(null)

  return (
    <Layout>
      <section style={{ padding: '30px 0 90px' }}>
        <h2 style={{ marginBottom: 24 }}>Saved items</h2>

        {savedLots.length === 0 ? (
          <div className="empty-state">
            <h3>Nothing saved yet</h3>
            <p>Tap the star on an auction to keep track of items you&rsquo;re watching.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 22 }}>
            {savedLots.map((lot) => (
              <AuctionCard key={lot.id} lot={lot} onOpen={setActiveLot} />
            ))}
          </div>
        )}
      </section>
      {activeLot && <AuctionModal lot={activeLot} onClose={() => setActiveLot(null)} />}
    </Layout>
  )
}
