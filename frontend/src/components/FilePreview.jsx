import { useEffect, useState } from 'react'

export default function FilePreview({ file, onRemove }) {
  const [preview, setPreview] = useState('')
  useEffect(() => {
    if (!file.type.startsWith('image/')) return undefined
    const url = URL.createObjectURL(file); setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])
  return <div className="file-preview">{preview ? <img src={preview} alt=""/> : <span className="file-preview-icon">DOC</span>}<span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB</small></span><button type="button" className="btn btn-ghost btn-sm" onClick={onRemove}>Remove</button></div>
}
