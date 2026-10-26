import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import { useData } from '../context/DataContext'

export default function OrderDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { orders, cancelOrder } = useData()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const order = orders.find((o) => String(o.id) === id)

  const cancel = async () => {
    if (!window.confirm('Cancel this unconfirmed order? You will give up the item.')) return
    setBusy(true); setError('')
    try { await cancelOrder(order.id); navigate('/orders') }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  if (!order) {
    return (
      <Layout>
        <div className="empty-state">
          <h3>Order not found</h3>
          <Link to="/orders" className="btn btn-outline" style={{ marginTop: 12 }}>
            Back to orders
          </Link>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <section style={{ padding: '30px 0 90px', maxWidth: 560 }}>
        <Link to="/orders" style={{ fontSize: 13, color: 'var(--text-soft)' }}>
          &larr; Back to order history
        </Link>
        <h2 style={{ margin: '18px 0 24px' }}>Order #{order.id}</h2>

        <div className="card" style={{ overflow: 'hidden' }}>
          <img
            src={order.lot.product_image || '/placeholder.svg'}
            alt=""
            style={{ width: '100%', height: 220, objectFit: 'cover', display: 'block' }}
          />
          <div style={{ padding: 22 }}>
            <h3 style={{ marginBottom: 8 }}>{order.lot.product_name}</h3>
            <p>{order.lot.event_title}</p>
            <div className="modal-meta-row">
              <span>Status: <strong>{order.status.replace('_', ' ')}</strong></span>
              <span>Final price: <strong>${order.final_price}</strong></span>
              <span>Won on: <strong>{new Date(order.created_at).toLocaleDateString()}</strong></span>
            </div>
            {order.status === 'AWAITING_CONFIRMATION' ? (
              <div style={{ marginTop: 18, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Link to="/orders" className="btn btn-primary">Fill delivery details</Link>
                <button className="btn btn-outline" disabled={busy} onClick={cancel}>{busy ? 'Cancelling…' : 'Cancel order'}</button>
              </div>
            ) : (
              <div className="field" style={{ marginTop: 18 }}>
                <label>Delivery details</label>
                <textarea className="textarea" value={`${order.delivery_full_name || ''}\n${order.shipping_address || ''}${order.delivery_city ? `, ${order.delivery_city}` : ''}\n${order.delivery_phone || ''}`} readOnly />
              </div>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
          </div>
        </div>
      </section>
    </Layout>
  )
}
