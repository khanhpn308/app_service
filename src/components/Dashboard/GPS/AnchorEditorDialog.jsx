import React, { useEffect, useState } from 'react'

const numericFields = ['x', 'y', 'z']
const coordinatePattern = /^-?\d*(?:\.\d{0,2})?$/
const macAddressPattern = /^(?:[0-9A-F]{2}:){5}[0-9A-F]{2}$/

function roundCoordinate(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return value
  return Math.round((number + Math.sign(number || 1) * Number.EPSILON) * 100) / 100
}

function normalizeCoordinates(anchor) {
  const normalized = numericFields.reduce(
    (current, field) => ({ ...current, [field]: roundCoordinate(current[field]) }),
    { ...anchor },
  )
  return { ...normalized, mac_address: String(anchor.mac_address || '').toUpperCase() }
}

export default function AnchorEditorDialog({ mode, anchor, onChange, onSave, onDelete, onClose }) {
  const [form, setForm] = useState(() => normalizeCoordinates(anchor))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => setForm(normalizeCoordinates(anchor)), [anchor, mode])

  function change(field, value) {
    if (numericFields.includes(field) && !coordinatePattern.test(value)) return
    const next = { ...form, [field]: field === 'mac_address' ? value.toUpperCase() : value }
    setForm(next)
    onChange?.(next)
  }

  async function submit(event) {
    event.preventDefault()
    const macAddress = String(form.mac_address || '').trim().toUpperCase()
    const name = String(form.name || '').trim()
    const values = Object.fromEntries(
      numericFields.map((field) => [field, roundCoordinate(form[field])]),
    )
    if (!macAddress || !name) {
      setError('MAC Address và tên Anchor là bắt buộc.')
      return
    }
    if (!macAddressPattern.test(macAddress)) {
      setError('MAC Address phải có dạng 12:21:AA:43:1A:9F.')
      return
    }
    if (numericFields.some((field) => !Number.isFinite(values[field]))) {
      setError('Tọa độ phải là số hợp lệ.')
      return
    }
    if (values.x < 0 || values.x > 100 || values.y < 0 || values.y > 100) {
      setError('Tọa độ X và Y phải nằm trong khoảng 0–100.')
      return
    }
    const payload = { mac_address: macAddress, name, ...values }
    if (mode === 'edit' && anchor.mac_address) delete payload.mac_address
    setBusy(true)
    setError('')
    try {
      await onSave(payload)
    } catch (saveError) {
      setError(saveError?.message || 'Không thể lưu Anchor.')
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm(`Xóa Anchor “${form.name}”?`)) return
    setBusy(true)
    setError('')
    try {
      await onDelete?.()
    } catch (deleteError) {
      setError(deleteError?.message || 'Không thể xóa Anchor.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-end bg-slate-950/20 p-4" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="anchor-editor-title"
        className="pointer-events-auto w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="anchor-editor-title" className="text-lg font-bold text-slate-900">
            {mode === 'create' ? 'Thêm Anchor' : 'Cấu hình Anchor'}
          </h2>
          <button type="button" onClick={onClose} aria-label="Đóng" className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100">✕</button>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <label className="block text-sm font-medium text-slate-700">
            MAC Address
            <input aria-label="MAC Address" placeholder="12:21:AA:43:1A:9F" maxLength={17} autoComplete="off" spellCheck={false} required disabled={mode === 'edit' && Boolean(anchor.mac_address)} value={form.mac_address ?? ''} onChange={(event) => change('mac_address', event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 font-mono uppercase disabled:bg-slate-100" />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Tên Anchor
            <input aria-label="Tên Anchor" required value={form.name ?? ''} onChange={(event) => change('name', event.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
          </label>
          <div className="grid w-full grid-cols-3 gap-2 sm:w-1/2">
            {numericFields.map((field) => (
              <label key={field} className="block text-sm font-medium uppercase text-slate-700">
                {field}
                <input aria-label={`Tọa độ ${field.toUpperCase()}`} type="number" step="0.01" min={field === 'z' ? undefined : 0} max={field === 'z' ? undefined : 100} required value={form[field] ?? ''} onChange={(event) => change(field, event.target.value)} className="mt-1 min-w-0 w-full rounded-lg border border-slate-300 px-1.5 py-2 text-sm [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none" />
              </label>
            ))}
          </div>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div className="flex items-center justify-between gap-3 pt-2">
            {mode === 'edit' ? <button type="button" disabled={busy} onClick={remove} className="rounded-lg px-3 py-2 text-sm font-semibold text-red-600 hover:bg-red-50">Xóa Anchor</button> : <span />}
            <div className="flex gap-2">
              <button type="button" disabled={busy} onClick={onClose} className="rounded-lg border border-slate-300 bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">Hủy</button>
              <button type="submit" disabled={busy} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{busy ? 'Đang lưu…' : 'Lưu Anchor'}</button>
            </div>
          </div>
        </form>
      </section>
    </div>
  )
}
