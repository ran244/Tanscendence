import { Link, useLocation } from 'react-router-dom'
import { useState } from 'react'
import Logo from '../components/Logo'
import SiteFooter from '../components/SiteFooter'
import { post } from '../api/client'

export default function CheckEmail() {
  const location = useLocation()
  const email = location.state?.email || ''
  const [message, setMessage] = useState(location.state?.message || 'Check your email to verify your account.')
  const [error, setError] = useState('')

  const resend = async () => {
    setError('')
    try { setMessage((await post('/accounts/auth/email/resend/', { email })).message) }
    catch (err) { setError(err.message) }
  }

  return <div className="auth-page"><div className="topbar"><Logo to="/" /></div><div className="auth-center"><div className="auth-card form-narrow"><h2>Check your email</h2><p role="status">{message}</p>{email && <p>We sent the verification link to <strong>{email}</strong>.</p>}{error && <p className="form-error" role="alert">{error}</p>}{email && <button className="btn btn-outline btn-block" type="button" onClick={resend}>Resend verification email</button>}<p><Link to="/login">Back to login</Link></p></div></div><SiteFooter /></div>
}
