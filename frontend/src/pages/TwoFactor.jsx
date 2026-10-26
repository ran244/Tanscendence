import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import SiteFooter from '../components/SiteFooter'
import { post } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function TwoFactor() {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { login } = useAuth()
  const submit = async (event) => { event.preventDefault(); try { await post('/accounts/auth/2fa/verify/', { code, recovery: code.length !== 6 }); window.location.assign('/') } catch (err) { setError(err.message) } }
  return <div className="auth-page"><div className="topbar"><Logo to="/" /></div><div className="auth-center"><div className="auth-card"><h2>Two-factor verification</h2><form onSubmit={submit} className="form-narrow">{error && <p role="alert" className="form-error">{error}</p>}<div className="field"><label htmlFor="code">Authenticator or recovery code</label><input id="code" className="input" value={code} onChange={(event) => setCode(event.target.value)} autoComplete="one-time-code" required /></div><button className="btn btn-primary btn-block">Verify</button></form></div></div><SiteFooter /></div>
}
