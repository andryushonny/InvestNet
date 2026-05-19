import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { View } from '../App';

export default function Cases({ setView }: { setView: (v: View) => void }) {
  const [cases, setCases] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', stage: '', geography: '', sector: '', ticket_range: '' });

  async function reload() { setCases(await api<any[]>('/cases')); }
  useEffect(() => { reload().catch(() => {}); }, []);

  async function create() {
    if (!form.title.trim() || !form.description.trim()) return;
    await api('/cases', { method: 'POST', body: JSON.stringify(form) });
    setForm({ title: '', description: '', stage: '', geography: '', sector: '', ticket_range: '' });
    setCreating(false);
    reload();
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Кейсы ({cases.length})</h1>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>+ Новый кейс</button>
      </div>
      {creating && (
        <div className="card space-y-3">
          <input className="input" placeholder="Заголовок (например, AI-стартап Series A)" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <textarea className="input min-h-32" placeholder="Описание кейса (рынок, traction, команда, что ищете)…" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <div className="grid grid-cols-4 gap-2">
            <input className="input" placeholder="Стадия (seed)" value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })} />
            <input className="input" placeholder="Сектор (AI)" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })} />
            <input className="input" placeholder="География (US, EU)" value={form.geography} onChange={(e) => setForm({ ...form, geography: e.target.value })} />
            <input className="input" placeholder="Чек ($50k–$500k)" value={form.ticket_range} onChange={(e) => setForm({ ...form, ticket_range: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={create}>Создать</button>
            <button className="btn" onClick={() => setCreating(false)}>Отмена</button>
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-4">
        {cases.map((c) => (
          <div key={c.id} className="card cursor-pointer hover:border-accent" onClick={() => setView({ name: 'case', id: c.id })}>
            <div className="font-semibold">{c.title}</div>
            <div className="text-muted text-sm mt-1 line-clamp-3">{c.description}</div>
            <div className="flex flex-wrap gap-2 mt-3">
              {c.stage && <span className="badge bg-[#1c2230]">{c.stage}</span>}
              {c.sector && <span className="badge bg-[#1c2230]">{c.sector}</span>}
              {c.geography && <span className="badge bg-[#1c2230]">{c.geography}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
