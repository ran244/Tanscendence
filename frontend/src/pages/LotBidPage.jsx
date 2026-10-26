import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AuctionModal from '../components/AuctionModal'
import Layout from '../components/Layout'
import { get } from '../api/client'
import { normalizeLot } from '../context/DataContext'

export default function LotBidPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [lot, setLot] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    get(`/auctions/lots/${id}/`)
      .then((data) => setLot(normalizeLot(data)))
      .catch((err) => setError(err.message))
  }, [id])

  return <Layout>
    <section style={{ padding: '30px 0 90px' }}>
      {error && <div className="empty-state"><h3>Lot unavailable</h3><p>{error}</p></div>}
      {!lot && !error && <div className="empty-state"><p>Loading lot…</p></div>}
    </section>
    {lot && <AuctionModal lot={lot} onClose={() => navigate('/my-bids')} />}
  </Layout>
}
