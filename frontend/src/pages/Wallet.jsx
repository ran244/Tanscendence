import Layout from '../components/Layout'

export default function Wallet() {
  return <Layout><section style={{ padding: '30px 0 90px', maxWidth: 620 }}>
    <h2>Payment</h2>
    <div className="panel"><h3>Cash on delivery</h3><p>Mystery Auctions does not store cards or use a payment provider. Winners confirm a delivery address and pay the courier upon delivery.</p></div>
  </section></Layout>
}
