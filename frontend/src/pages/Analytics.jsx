import { useEffect, useState } from 'react'
import Layout from '../components/Layout'
import { get } from '../api/client'

export default function Analytics() {
  const [data, setData] = useState(null); const [error, setError] = useState('')
  const today = new Date().toISOString().slice(0, 10)
  const prior = new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10)
  const [range, setRange] = useState({ from: prior, to: today })
  const load = () => get(`/analytics/dashboard/?from=${range.from}&to=${range.to}T23:59:59`).then(setData).catch((err) => setError(err.message))
  useEffect(() => { load() }, [])
  const maxBids = Math.max(1, ...(data?.time_series || []).map((row) => row.bids))
  const exportUrl = `/api/analytics/export/?format=csv&from=${range.from}&to=${range.to}T23:59:59`
  return <Layout><section style={{ padding: '30px 0 90px' }}><div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}><h2>Sales analytics</h2><a className="btn btn-outline btn-sm" href={exportUrl}>Download CSV</a></div><form onSubmit={(event) => { event.preventDefault(); load() }} style={{ display: 'flex', gap: 12, alignItems: 'end', flexWrap: 'wrap', marginBottom: 24 }}><div className="field"><label>From</label><input className="input" type="date" value={range.from} onChange={(event) => setRange({ ...range, from: event.target.value })} /></div><div className="field"><label>To</label><input className="input" type="date" value={range.to} onChange={(event) => setRange({ ...range, to: event.target.value })} /></div><button className="btn btn-primary">Apply range</button></form>{error && <p className="form-error">{error}</p>}{data && <><div className="stats-grid">{Object.entries(data.totals).map(([key, value]) => <div className="panel" key={key}><div className="sub">{key.replaceAll('_', ' ')}</div><h3>{value}</h3></div>)}</div><h3>Daily activity</h3>{data.time_series.length === 0 ? <div className="empty-state"><p>No activity in this date range.</p></div> : <div className="panel" aria-label="Daily accepted bids chart">{data.time_series.map((row) => <div key={row.date} style={{ display: 'grid', gridTemplateColumns: '90px 1fr 80px', gap: 10, alignItems: 'center', margin: '10px 0' }}><span>{row.date.slice(5)}</span><div style={{ height: 18, background: 'var(--border)', borderRadius: 9 }}><div style={{ height: '100%', width: `${Math.max(3, row.bids / maxBids * 100)}%`, background: 'var(--accent)', borderRadius: 9 }} /></div><span>{row.bids} bids</span></div>)}</div>}{data.time_series.map((row) => <div className="list-row" key={row.date}><div className="flex1"><strong>{row.date}</strong></div><span>{row.bids} bids</span><span className="amount">${row.revenue}</span></div>)}</>}</section></Layout>
}
