import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import { useData } from '../context/DataContext'

export default function Cart() {
  const { awaitingPaymentOrders, confirmCod } = useData()
  const [address, setAddress] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const total = awaitingPaymentOrders.reduce((sum, order) => sum + Number(order.final_price), 0)

  const confirmAll = async () => {
    if (!address.trim()) return setError('Enter the delivery address first.')
    try {
      for (const order of awaitingPaymentOrders) await confirmCod(order.id, address)
      navigate('/orders')
    } catch (err) { setError(err.message) }
  }

  return <Layout><section style={{ padding: '30px 0 90px', maxWidth: 620 }}>
    <h2>Cash on delivery confirmation</h2>
    <p>No online payment or card is required. Pay the courier when your order is delivered.</p>
    {awaitingPaymentOrders.length === 0 ? <div className="empty-state"><h3>No orders awaiting confirmation</h3></div> : <>
      {awaitingPaymentOrders.map((order) => <div key={order.id} className="cart-row">
        <img src={order.lot.product.image} alt="" /><div className="flex1"><h4>{order.lot.product.name}</h4><small>Order #{order.id}</small></div><span className="amount">${order.final_price}</span>
      </div>)}
      <div className="cart-summary"><span>Cash due on delivery</span><span>${total.toFixed(2)}</span></div>
      <div className="field" style={{ marginTop: 20 }}><label htmlFor="delivery-address">Delivery address</label><textarea id="delivery-address" className="input" value={address} onChange={(event) => setAddress(event.target.value)} required /></div>
      {error && <p role="alert" className="form-error">{error}</p>}
      <button className="btn btn-primary" onClick={confirmAll}>Confirm cash on delivery</button>
    </>}
  </section></Layout>
}
