import { Link } from 'react-router-dom'
import logo from '../assets/logo.png'

export default function Logo({ to = '/' }) {
  return (
    <Link to={to} className="logo-mark">
      <img src={logo} alt="Mystery Auctions" />
      <span className="logo-wordmark">
        MYSTERY
        <br />
        AUCTIONS
        <small>Artifact &amp; Curiosity Sale</small>
      </span>
    </Link>
  )
}
