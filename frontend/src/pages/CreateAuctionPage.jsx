import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Layout from '../components/Layout'
import FilePreview from '../components/FilePreview'
import { del, get, patch, post, upload as uploadFile } from '../api/client'

const localTime = (date = new Date(Date.now() + 2 * 3600000)) => { const value = new Date(date); value.setMinutes(value.getMinutes() - value.getTimezoneOffset()); return value.toISOString().slice(0, 16) }
const blankLot = () => ({ name: '', description: '', category: '', starting_price: '', minimum_increment: '1.00', image: null, attachments: [], uploadProgress: 0 })

export default function CreateAuctionPage() {
  const { id } = useParams(); const editing = Boolean(id); const navigate = useNavigate()
  const [categories, setCategories] = useState([])
  const [form, setForm] = useState({ title: '', description: '', start_time: localTime(), end_time: localTime(new Date(Date.now() + 26 * 3600000)) })
  const [lots, setLots] = useState([blankLot()]); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  useEffect(() => { Promise.all([get('/products/categories/?page_size=100'), editing ? get(`/auctions/events/${id}/`) : Promise.resolve(null)]).then(([page, event]) => { const rows = page.results || page; setCategories(rows); if (event) { setForm({ title: event.title, description: event.description, start_time: localTime(event.start_time), end_time: localTime(event.end_time) }); setLots(event.lots.map((lot) => ({ id: lot.id, product: lot.product, name: lot.product_name, starting_price: lot.starting_price, minimum_increment: lot.minimum_increment }))) } else if (rows[0]) setLots([{ ...blankLot(), category: String(rows[0].id) }]) }).catch((err) => setError(err.message)) }, [editing, id])
  const setEvent = (key) => (e) => setForm((old) => ({ ...old, [key]: e.target.value }))
  const setLot = (index, key, value) => setLots((old) => old.map((lot, i) => i === index ? { ...lot, [key]: value } : lot))
  const uploadProductFiles = async (product, lot, index) => {
    if (lot.image) {
      const imageUpload = new FormData(); imageUpload.append('image', lot.image); imageUpload.append('is_primary', 'true'); imageUpload.append('alt_text', lot.name)
      await uploadFile(`/products/${product.id}/images/`, imageUpload, (progress) => setLot(index, 'uploadProgress', Math.round(progress / 2)))
    }
    for (let fileIndex = 0; fileIndex < lot.attachments.length; fileIndex += 1) {
      const attachmentUpload = new FormData(); attachmentUpload.append('file', lot.attachments[fileIndex])
      await uploadFile(`/products/${product.id}/attachments/`, attachmentUpload, (progress) => setLot(index, 'uploadProgress', Math.round(((fileIndex + progress / 100) / lot.attachments.length) * 100)))
    }
    setLot(index, 'uploadProgress', 100)
  }
  const persist = async (e, saveOnly = false) => {
    e?.preventDefault(); setBusy(true); setError('')
    try {
      if (!lots.length) throw new Error('An auction event must contain at least one lot.')
      const startDate = new Date(form.start_time); const endDate = new Date(form.end_time)
      const diffMinutes = (endDate.getTime() - startDate.getTime()) / 60000
      if (diffMinutes < 30) throw new Error('Bidding duration must be at least 30 minutes.')
      if (diffMinutes > 24 * 60) throw new Error('Bidding duration cannot exceed 24 hours.')
      const start = startDate.toISOString(); const end = endDate.toISOString()
      if (editing) {
        await patch(`/auctions/events/${id}/`, { ...form, start_time: start, end_time: end })
        const current = await get(`/auctions/events/${id}/`); const kept = new Set(lots.filter((lot) => lot.id).map((lot) => lot.id))
        await Promise.all(current.lots.filter((lot) => !kept.has(lot.id)).map((lot) => del(`/auctions/events/${id}/lots/${lot.id}/`)))
        for (let index = 0; index < lots.length; index += 1) {
          const lot = lots[index]; const payload = { lot_number: index + 1, starting_price: lot.starting_price, minimum_increment: lot.minimum_increment, start_time: start, end_time: end }
          if (lot.id) await patch(`/auctions/events/${id}/lots/${lot.id}/`, payload)
          else { const product = await post('/products/', { name: lot.name, description: lot.description, category: Number(lot.category), available: true }); await uploadProductFiles(product, lot, index); await post(`/auctions/events/${id}/lots/`, { ...payload, product: product.id }) }
        }
        if (!saveOnly) await post(`/auctions/events/${id}/submit/`)
      } else {
        const products = []
        for (let index = 0; index < lots.length; index += 1) { const lot = lots[index]; const product = await post('/products/', { name: lot.name, description: lot.description, category: Number(lot.category), available: true }); await uploadProductFiles(product, lot, index); products.push(product) }
        const auction = await post('/auctions/events/', { ...form, start_time: start, end_time: end, lots: lots.map((lot, index) => ({ product: products[index].id, lot_number: index + 1, starting_price: lot.starting_price, minimum_increment: lot.minimum_increment, start_time: start, end_time: end })) })
        if (!saveOnly) await post(`/auctions/events/${auction.id}/submit/`)
      }
      navigate('/my-auctions')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <Layout><section style={{ padding: '30px 0 90px', maxWidth: 820 }}><h2>{editing ? 'Edit auction revision' : 'Create auction event'}</h2><p>Your work is not stored until you choose Save draft or Submit for approval. Private drafts never appear in the admin workspace.</p><form onSubmit={(e) => persist(e, false)}>
    <div className="auction-form-grid"><div className="field field-full"><label>Event name</label><input className="input" value={form.title} onChange={setEvent('title')} required /></div><div className="field field-full"><label>Event description</label><textarea className="textarea" value={form.description} onChange={setEvent('description')} /></div><div className="field"><label>Starts</label><input className="input" type="datetime-local" value={form.start_time} onChange={setEvent('start_time')} required /></div><div className="field"><label>Ends</label><input className="input" type="datetime-local" value={form.end_time} onChange={setEvent('end_time')} required /></div></div>
    {lots.map((lot, index) => <fieldset className="panel" style={{ margin: '22px 0', padding: 20 }} key={lot.id || index}><legend><strong>Lot {index + 1}</strong></legend><div className="auction-form-grid"><div className="field"><label>Item name</label><input className="input" value={lot.name} onChange={(e) => setLot(index, 'name', e.target.value)} disabled={Boolean(lot.id)} required /></div>{!lot.id && <div className="field"><label>Category</label><select className="input" value={lot.category} onChange={(e) => setLot(index, 'category', e.target.value)} required>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></div>}{!lot.id && <><div className="field field-full"><label>Item description</label><textarea className="textarea" value={lot.description} onChange={(e) => setLot(index, 'description', e.target.value)} /></div><div className="field field-full"><label>Primary image (optional)</label><input className="input" type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={(e) => setLot(index, 'image', e.target.files?.[0] || null)} />{lot.image && <FilePreview file={lot.image} onRemove={() => setLot(index, 'image', null)} />}</div><div className="field field-full"><label>Attachments (optional)</label><input className="input" type="file" multiple accept=".jpg,.jpeg,.png,.webp,.gif,.pdf,.txt,.csv,.docx" onChange={(e) => setLot(index, 'attachments', [...(e.target.files || [])])} /><small>Images and documents, up to 10 MB each.</small>{lot.attachments.map((file, fileIndex) => <FilePreview key={`${file.name}-${fileIndex}`} file={file} onRemove={() => setLot(index, 'attachments', lot.attachments.filter((_, i) => i !== fileIndex))} />)}{busy && lot.uploadProgress > 0 && <div className="upload-progress"><span style={{ width: `${lot.uploadProgress}%` }} /><small>{lot.uploadProgress}% uploaded</small></div>}</div></>}<div className="field"><label>Starting price</label><input className="input" type="number" min="0.01" step="0.01" value={lot.starting_price} onChange={(e) => setLot(index, 'starting_price', e.target.value)} required /></div><div className="field"><label>Minimum increment</label><input className="input" type="number" min="0.01" step="0.01" value={lot.minimum_increment} onChange={(e) => setLot(index, 'minimum_increment', e.target.value)} required /></div></div>{lots.length > 1 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLots((old) => old.filter((_, i) => i !== index))}>Remove lot</button>}</fieldset>)}
    <button type="button" className="btn btn-outline" onClick={() => setLots((old) => [...old, { ...blankLot(), category: String(categories[0]?.id || '') }])}>+ Add another lot</button>{error && <p className="form-error" role="alert">{error}</p>}<div style={{ display: 'flex', gap: 12, marginTop: 18 }}><button type="button" className="btn btn-outline" onClick={() => persist(null, true)} disabled={busy}>{busy ? 'Saving…' : 'Save draft'}</button><button className="btn btn-primary" disabled={busy}>{busy ? 'Submitting…' : editing ? 'Submit revision for approval' : 'Submit event for approval'}</button></div>
  </form></section></Layout>
}
