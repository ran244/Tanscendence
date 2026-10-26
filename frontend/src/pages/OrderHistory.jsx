import { useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import { useData } from '../context/DataContext'

export default function OrderHistory() {
  const { orders, confirmCod } = useData()
  const [selectedOrder, setSelectedOrder] = useState(null)
  const [deliveryForm, setDeliveryForm] = useState({
    fullName: '',
    address: '',
    city: '',
    phone: '',
    preferredDate: '',
    notes: ''
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleConfirmDelivery = async (e) => {
    e.preventDefault()
    if (!deliveryForm.address.trim() || !deliveryForm.city.trim() || !deliveryForm.phone.trim()) {
      return setError('Please fill in all required delivery details.')
    }
    setBusy(true); setError('')
    try {
      await confirmCod(selectedOrder.id, {
        delivery_full_name: deliveryForm.fullName,
        shipping_address: deliveryForm.address,
        delivery_city: deliveryForm.city,
        delivery_phone: deliveryForm.phone,
        preferred_delivery_at: deliveryForm.preferredDate || null,
        delivery_notes: deliveryForm.notes,
      })
      setSelectedOrder(null)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <Layout>
      <section className="order-history-page" style={{ padding: '30px 0 90px' }}>
        <h2 style={{ marginBottom: 24 }}>Order history</h2>

        {orders.length === 0 ? (
          <div className="empty-state">
            <h3>No orders yet</h3>
            <p>Auctions you win will show up here once they&rsquo;re settled.</p>
          </div>
        ) : (
          orders.map((o) => (
            <div key={o.id} className="list-row order-history-row" style={{ alignItems: 'center' }}>
              <img src={o.lot.product_image || '/placeholder.svg'} alt="" />
              <div className="flex1">
                <h4>{o.lot.product_name}</h4>
                <div className="sub">
                  Order #{o.id} &middot; {new Date(o.created_at).toLocaleDateString()}
                </div>
              </div>
              <span className={`tag ${o.status === 'AWAITING_CONFIRMATION' ? 'tag-upcoming' : 'tag-live'}`}>
                {o.status.replaceAll('_', ' ')}
              </span>
              <span className="amount">${o.final_price}</span>
              {o.status === 'AWAITING_CONFIRMATION' ? (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => {
                    setSelectedOrder(o)
                    setDeliveryForm({ fullName: '', address: '', city: '', phone: '', preferredDate: '', notes: '' })
                  }}
                >
                  Fill Delivery Details
                </button>
              ) : (
                <Link to={`/orders/${o.id}`} className="btn btn-outline btn-sm">
                  View details
                </Link>
              )}
            </div>
          ))
        )}

        {selectedOrder && (
          <div className="drawer-backdrop" onClick={() => setSelectedOrder(null)}>
            <div
              className="modal-card panel"
              onClick={(e) => e.stopPropagation()}
              style={{ maxWidth: 500, margin: '60px auto', padding: 24, position: 'relative', zIndex: 10001 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3>Delivery Details for Order #{selectedOrder.id}</h3>
                <button className="close-x-btn" onClick={() => setSelectedOrder(null)}>✕</button>
              </div>
              <form onSubmit={handleConfirmDelivery}>
                <div className="field">
                  <label>Full Name</label>
                  <input className="input" value={deliveryForm.fullName} onChange={(e) => setDeliveryForm({ ...deliveryForm, fullName: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Street Address</label>
                  <input className="input" value={deliveryForm.address} onChange={(e) => setDeliveryForm({ ...deliveryForm, address: e.target.value })} required />
                </div>
                <div className="field">
                  <label>City / Area</label>
                  <input className="input" value={deliveryForm.city} onChange={(e) => setDeliveryForm({ ...deliveryForm, city: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Phone Number</label>
                  <input className="input" type="tel" value={deliveryForm.phone} onChange={(e) => setDeliveryForm({ ...deliveryForm, phone: e.target.value })} required />
                </div>
                <div className="field">
                  <label>Preferred Delivery Date & Time (Optional)</label>
                  <input className="input" type="datetime-local" value={deliveryForm.preferredDate} onChange={(e) => setDeliveryForm({ ...deliveryForm, preferredDate: e.target.value })} />
                </div>
                <div className="field">
                  <label>Additional Delivery Instructions (Optional)</label>
                  <textarea className="textarea" value={deliveryForm.notes} onChange={(e) => setDeliveryForm({ ...deliveryForm, notes: e.target.value })} />
                </div>
                {error && <p className="form-error" role="alert">{error}</p>}
                <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                  <button type="button" className="btn btn-ghost" onClick={() => setSelectedOrder(null)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Submitting…' : 'Send details to seller'}</button>
                </div>
              </form>
            </div>
          </div>
        )}
      </section>
    </Layout>
  )
}
