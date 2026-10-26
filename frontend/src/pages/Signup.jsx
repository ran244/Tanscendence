import { Link, useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import SplashScreen from '../components/SplashScreen'
import SiteFooter from '../components/SiteFooter'
import { useAuth } from '../context/AuthContext'
import { useState } from 'react'

import { useEffect } from 'react'

export default function Signup() {
  const { signup, showSplash } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ first_name: '', last_name: '', username: '', email: '', password: '', password_confirm: '' })
  const [error, setError] = useState('')
  const [expired, setExpired] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setExpired(true)
      setError('your sign up or login session has finished please reload too attempt again')
    }, 10 * 60 * 1000)
    return () => clearTimeout(timer)
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (expired) {
      setError('your sign up or login session has finished please reload too attempt again')
      return
    }
    setError('')
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (form.password !== form.password_confirm) {
      setError('Passwords do not match.')
      return
    }
    try {
      const result = await signup(form)
      navigate('/signup/check-email', { state: { email: form.email, message: result.message } })
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="auth-page">
      {showSplash && <SplashScreen />}
      <div className="topbar">
        <Logo to="/signup" />
      </div>
      <div className="auth-center">
        <div className="auth-card">
          <form onSubmit={handleSubmit} className="form-narrow">
            {error && <p role="alert" className="form-error">{error}</p>}
            <div className="field">
              <input className="input" placeholder="First Name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
            </div>
            <div className="field">
              <input className="input" placeholder="Last Name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
            </div>
            <div className="field">
              <input className="input" placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            </div>
            <div className="field">
              <input className="input" type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </div>
            <div className="field">
              <input className="input" type="password" placeholder="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            </div>
            <div className="field">
              <input className="input" type="password" placeholder="confirm password" minLength={8} value={form.password_confirm} onChange={(e) => setForm({ ...form, password_confirm: e.target.value })} required />
            </div>
            <button className="btn btn-outline btn-block" type="submit" style={{ marginTop: 20 }}>
              confirm sign up
            </button>
          </form>
        </div>
      </div>
      <div className="auth-footer">
        Already have an account? <Link to="/login">Log in.</Link>
      </div>
      <SiteFooter />
    </div>
  )
}
