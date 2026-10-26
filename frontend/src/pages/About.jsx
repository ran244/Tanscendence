import Layout from '../components/Layout'
import { Link } from 'react-router-dom'

export default function About() {
  return <Layout><article className="legal-page about-page">
    <span className="eyebrow">Our story</span>
    <h1>About Mystery Auctions</h1>
    <p>Mystery Auctions is a curated online auction house for artifacts, jewelry, manuscripts, collectibles and unusual objects. We bring organizers and collectors together through transparent, timed bidding events.</p>
    <h2>What we offer</h2>
    <p>Participants can explore upcoming and live auctions, review individual lots, place bids in real time, save favorites and follow their orders. Organizers can create multi-lot auction events and submit them for review before they are made public.</p>
    <h2>Trust and transparency</h2>
    <p>Every auction is reviewed by an administrator. Bid histories are maintained per lot, event activity is communicated in real time, and account safeguards include email verification, secure sessions and optional two-factor authentication.</p>
    <h2>Built around collectors</h2>
    <p>Member profiles, friendships, online presence and private friend messaging help collectors stay connected while keeping auction and account permissions clearly separated.</p>
    <h2>Contact us</h2>
    <p>Questions or concerns can be sent through the <Link to="/report-issue">Report an issue</Link> page. Mystery Auctions is based in Amman, Jordan.</p>
  </article></Layout>
}
