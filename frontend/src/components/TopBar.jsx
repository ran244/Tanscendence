import { useState } from 'react'
import { Link } from 'react-router-dom'
import Logo from './Logo'
import ThemeToggle from './ThemeToggle'
import ProfileDrawer from './ProfileDrawer'
import { HomeIcon, UserCircle } from './Icons'
import { useAuth } from '../context/AuthContext'

export default function TopBar() {
  const { user, loading } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)

  return (
    <header className="topbar">
      <Logo to={user?.role === 'ADMIN' ? '/admin' : '/'} />
      <div className="topbar-right">
        {user && user.role !== 'ADMIN' && <Link to="/" className="home-link" aria-label="Home" title="Home"><HomeIcon /></Link>}
        {user?.role === 'ADMIN' && <Link to="/admin" className="btn btn-primary btn-sm">Admin workspace</Link>}
        <ThemeToggle />
        {loading ? (
          <span className="profile-loading" aria-label="Loading account" />
        ) : user ? (
          <button
            className="profile-trigger"
            onClick={() => setDrawerOpen(true)}
            aria-haspopup="true"
            aria-expanded={drawerOpen}
          >
            <img className="avatar" src={user.avatar || '/default-avatar.svg'} alt="" />
            <span className="profile-name">{user.username}</span>
          </button>
        ) : (
          <div className="anonymous-profile">
            <Link to="/login" className="profile-trigger" aria-label="Log in">
              <UserCircle />
            </Link>
            <span className="auth-prompt">
              <Link to="/login">Log in</Link>
              <span>or</span>
              <Link to="/signup">sign up</Link>
            </span>
          </div>
        )}
      </div>
      {drawerOpen && <ProfileDrawer onClose={() => setDrawerOpen(false)} />}
    </header>
  )
}
