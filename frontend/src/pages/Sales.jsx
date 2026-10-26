import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { get, patch } from '../api/client'

const nextStatus = { CONFIRMED: 'DELIVERED', PROCESSING: 'SHIPPED', SHIPPED: 'DELIVERED' }
export default function Sales() {
  const [orders, setOrders] = useState([]); const [error, setError] = useState('')
  const load = () => get('/orders/?role=seller&page_size=100').then((data) => setOrders(data.results || [])).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])
  const advance = async (order) => { try { const target = nextStatus[order.status]; const note = target === 'DELIVERED' ? window.prompt('Optional cash collection note') || '' : ''; await patch(`/orders/${order.id}/fulfill/`, { status: target, collection_note: note }); load() } catch (err) { setError(err.message) } }
  const collectionFailed = async (order) => {
    const note = window.prompt('Why could cash not be collected?')?.trim()
    if (!note) return
    try { await patch(`/orders/${order.id}/fulfill/`, { status: 'CANCELLED', collection_note: note }); load() }
    catch (err) { setError(err.message) }
  }
  return <Layout><section style={{ padding: '30px 0 90px' }}><h2>Seller orders</h2><p>Review the winner’s delivery request. The lot is sold only when you accept and complete the order.</p>{error && <p className="form-error">{error}</p>}{orders.length === 0 ? <div className="empty-state"><h3>No sales yet</h3></div> : orders.map((order) => <div className="list-row" key={order.id}><img src={order.lot.product_image || '/placeholder.svg'} alt=""/><div className="flex1"><h4>{order.lot.product_name}</h4><div className="sub">Buyer: {order.buyer_username} · {order.shipping_address ? `${order.delivery_full_name || order.buyer_username}, ${order.shipping_address}, ${order.delivery_city || ''} · ${order.delivery_phone || ''}` : 'Awaiting buyer delivery details'}</div>{order.preferred_delivery_at && <div className="sub">Preferred delivery: {new Date(order.preferred_delivery_at).toLocaleString()}</div>}{order.delivery_notes && <div className="sub">Notes: {order.delivery_notes}</div>}</div><span className="tag tag-upcoming">{order.status_display}</span><span className="amount">${order.final_price}</span>{nextStatus[order.status] && <button className="btn btn-primary btn-sm" onClick={() => advance(order)}>{order.status === 'CONFIRMED' ? 'Accept & complete order' : `Mark ${nextStatus[order.status].toLowerCase()}`}</button>}{order.status === 'SHIPPED' && <button className="btn btn-outline btn-sm" onClick={() => collectionFailed(order)}>Cash not collected</button>}</div>)}</section></Layout>
}
