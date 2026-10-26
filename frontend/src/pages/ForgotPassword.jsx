import { useNavigate } from 'react-router-dom'
import Logo from '../components/Logo'
import { useState } from 'react'
import { post } from '../api/client'

export default function ForgotPassword() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      const result = await post('/accounts/auth/password/reset/request/', { email })
      setMessage(result.message)
    } catch (err) { setError(err.message) }
  }

  return (
    <div className="auth-page">
      <div className="topbar">
        <Logo to="/login" />
      </div>
      <div className="auth-center">
        <div className="auth-card">
          <p className="auth-title">reset password using email</p>
          <form onSubmit={handleSubmit} className="form-narrow">
            {error && <p className="form-error" role="alert">{error}</p>}
            {message && <p>{message}</p>}
            <div className="field">
              <input className="input" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </div>
            <button className="btn btn-outline btn-block" type="submit" style={{ marginTop: 12 }}>
              Next
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
