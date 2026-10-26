import { Link, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import Logo from '../components/Logo'
import SplashScreen from '../components/SplashScreen'
import SiteFooter from '../components/SiteFooter'
import { useAuth } from '../context/AuthContext'

import { useEffect } from 'react'

export default function Login() {
  const { login, showSplash } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
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
    try {
      const result = await login(email, password)
      if (result.two_factor_required) return navigate('/login/2fa')
      navigate(result.user?.role === 'ADMIN' ? '/admin' : '/')
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="auth-page">
      {showSplash && <SplashScreen />}
      <div className="topbar">
        <Logo to="/login" />
      </div>
      <div className="auth-center">
        <div className="auth-card">
          <form onSubmit={handleSubmit} className="form-narrow">
            {error && <p role="alert" className="form-error">{error}</p>}
            <div className="field">
              <label htmlFor="email">Email:</label>
              <input id="email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
            </div>
            <div className="field">
              <label htmlFor="password">Password:</label>
              <input id="password" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </div>
            <button className="btn btn-outline btn-block" type="submit">
              sign in
            </button>
          </form>
        </div>
      </div>
      <div className="auth-footer">
        Don&apos;t have an account? <Link to="/signup">Sign up.</Link>
      </div>
      <SiteFooter />
    </div>
  )
}
