import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const commonLinks = [
  { to: '/account', label: 'Account information' },
  { to: '/notifications', label: 'Notifications' },
]

const participantLinks = [
  { to: '/friends', label: 'Friends' },
  { to: '/my-bids', label: 'My bids' },
  { to: '/my-auctions', label: 'My auctions' },
  { to: '/sales', label: 'Seller orders' },
  { to: '/orders', label: 'Order history' },
  { to: '/saved', label: 'Saved items' },
]

export default function ProfileDrawer({ onClose }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  const handleLogout = () => {
    logout()
    onClose()
    navigate('/login')
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="profile-drawer">
        <img className="avatar-lg" src={user.avatar || '/default-avatar.svg'} alt="" />
        <div className="username">{user.first_name || user.last_name ? `${user.first_name} ${user.last_name}`.trim() : user.username}</div>
        <div style={{ fontSize: 13, color: 'var(--text-soft)', marginBottom: 12 }}>@{user.username}</div>
        {[commonLinks[0], ...(user.role === 'ADMIN' ? [] : participantLinks), commonLinks[1]].map((l) => (
          <Link key={l.to} to={l.to} className="drawer-link" onClick={onClose}>
            {l.label}
          </Link>
        ))}
        {user.role === 'ADMIN' && <Link to="/admin" className="drawer-link" onClick={onClose}>Admin workspace</Link>}
        <div className="drawer-spacer" />
        <button className="drawer-logout" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </>
  )
}
