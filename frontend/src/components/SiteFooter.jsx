import { Link } from 'react-router-dom'
import Logo from './Logo'

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <Logo />
          <p>
            A curated house of artifacts, jewelry, manuscripts and
            curiosities, sold at auction to those who know what they&rsquo;re
            looking at.
          </p>
        </div>
        <div className="footer-col">
          <h4>Company</h4>
          <Link to="/about">About us</Link>
          {/* <Link to="/terms">Auction rules</Link> */}
        </div>
        <div className="footer-col">
          <h4>Support</h4>
          <Link to="/report-issue">Report an issue</Link>
        </div>
        <div className="footer-col">
          <h4>Legal</h4>
          <Link to="/terms">Terms of service</Link>
          <Link to="/privacy">Privacy policy</Link>
          {/* <Link to="/terms">Auction rules</Link> */}
        </div>
      </div>
      <div className="footer-bottom">
        <span>&copy; {new Date().getFullYear()} Mystery Auctions. All rights reserved.</span>
        <span>Amman, Jordan</span>
      </div>
    </footer>
  )
}
