import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { get, post } from '../api/client'

export default function Security() {
  const [setup, setSetup] = useState(null); const [code, setCode] = useState(''); const [password, setPassword] = useState(''); const [codes, setCodes] = useState([]); const [message, setMessage] = useState(''); const [error, setError] = useState('')
  const load = () => get('/accounts/me/2fa/setup/').then(setSetup).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])
  const enable = async () => { try { const result = await post('/accounts/me/2fa/enable/', { code }); setCodes(result.recovery_codes); setMessage(result.message); load() } catch (err) { setError(err.message) } }
  const disable = async () => { try { const result = await post('/accounts/me/2fa/disable/', { code, password }); setMessage(result.message); setCode(''); setPassword(''); load() } catch (err) { setError(err.message) } }
  return <Layout><section style={{ padding: '30px 0 90px', maxWidth: 620 }}><h2>Account security</h2>{error && <p className="form-error">{error}</p>}{message && <p role="status">{message}</p>}{setup && (setup.enabled ? <div className="panel"><h3>Two-factor authentication is enabled</h3><div className="field"><label>Authenticator code (or enter password below)</label><input className="input" value={code} onChange={(event) => setCode(event.target.value)} /></div><div className="field"><label>Password</label><input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></div><button className="btn btn-outline" onClick={disable}>Disable 2FA</button></div> : <div className="panel"><h3>Enable authenticator 2FA</h3><p>Enter this secret in your authenticator application:</p><code style={{ overflowWrap: 'anywhere' }}>{setup.secret}</code><div dangerouslySetInnerHTML={{ __html: setup.qr_svg }} /><div className="field"><label>Six-digit code</label><input className="input" inputMode="numeric" value={code} onChange={(event) => setCode(event.target.value)} /></div><button className="btn btn-primary" onClick={enable}>Enable 2FA</button></div>)}{codes.length > 0 && <div className="panel"><h3>Save these one-time recovery codes</h3><ul>{codes.map((value) => <li key={value}><code>{value}</code></li>)}</ul></div>}</section></Layout>
}
