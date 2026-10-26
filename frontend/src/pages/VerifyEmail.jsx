import { Link, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Logo from '../components/Logo'
import SiteFooter from '../components/SiteFooter'
import { get } from '../api/client'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const [state, setState] = useState({ loading: true, message: 'Verifying your email…', error: '' })

  useEffect(() => {
    const token = params.get('code')
    if (!token) { setState({ loading: false, message: '', error: 'This verification link is missing its token.' }); return }
    get(`/accounts/auth/email/verify/?code=${encodeURIComponent(token)}`)
      .then((result) => setState({ loading: false, message: result.message, error: '' }))
      .catch((err) => setState({ loading: false, message: '', error: err.message }))
  }, [params])

  return <div className="auth-page"><div className="topbar"><Logo to="/" /></div><div className="auth-center"><div className="auth-card form-narrow"><h2>Email verification</h2>{state.message && <p role="status">{state.message}</p>}{state.error && <p className="form-error" role="alert">{state.error}</p>}{!state.loading && <p><Link className="btn btn-outline btn-block" to="/login">Go to login</Link></p>}</div></div><SiteFooter /></div>
}
