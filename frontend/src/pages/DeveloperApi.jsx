import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { del, get, post } from '../api/client'

export default function DeveloperApi() {
  const [keys, setKeys] = useState([]); const [name, setName] = useState(''); const [plaintext, setPlaintext] = useState(''); const [error, setError] = useState('')
  const load = () => get('/common/api-keys/').then((data) => setKeys(data.results || [])).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])
  const create = async (event) => { event.preventDefault(); try { const result = await post('/common/api-keys/', { name }); setPlaintext(result.key); setName(''); load() } catch (err) { setError(err.message) } }
  const remove = async (id) => { try { await del(`/common/api-keys/${id}/`); load() } catch (err) { setError(err.message) } }
  return <Layout><section style={{ padding: '30px 0 90px', maxWidth: 760 }}><h2>Developer API keys</h2><p>Send a key as <code>X-API-Key</code> to the versioned <code>/api/v1/</code> endpoints. The plaintext is shown only once.</p><form onSubmit={create} style={{ display: 'flex', gap: 10 }}><input className="input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Key name" required/><button className="btn btn-primary">Create key</button></form>{plaintext && <div className="panel" role="status"><strong>Copy now:</strong><code style={{ display: 'block', overflowWrap: 'anywhere' }}>{plaintext}</code></div>}{error && <p className="form-error">{error}</p>}{keys.map((key) => <div className="list-row" key={key.id}><div className="flex1"><h4>{key.name}</h4><div className="sub">{key.prefix}… · last used {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : 'never'}</div></div><button className="btn btn-ghost btn-sm" onClick={() => remove(key.id)}>Revoke</button></div>)}</section></Layout>
}
