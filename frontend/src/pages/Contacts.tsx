import { useEffect, useState } from 'react';
import { api, streamTask } from '../lib/api';
import type { View } from '../App';

export default function Contacts({ setView }: { setView: (v: View) => void }) {
  const [q, setQ] = useState('');
  const [data, setData] = useState<any>({ total: 0, items: [] });
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);

  async function reload() {
    const r = await api<any>(`/persons?limit=200&q=${encodeURIComponent(q)}`);
    setData(r);
  }
  useEffect(() => { reload().catch(() => {}); }, [q]);

  function toggle(id: number) {
    const s = new Set(selected);
    if (s.has(id)) s.delete(id); else s.add(id);
    setSelected(s);
  }

  async function bulkEnrich() {
    if (selected.size === 0) return;
    setBusy(true);
    try {
      const { task_id } = await api<any>('/persons/enrich-batch', {
        method: 'POST',
        body: JSON.stringify({ person_ids: Array.from(selected) }),
      });
      await streamTask(task_id, () => {});
      setSelected(new Set());
      reload();
    } catch (e: any) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Контакты ({data.total})</h1>
      <div className="flex items-center gap-3">
        <input className="input max-w-md" placeholder="Поиск по имени, email, компании…" value={q} onChange={(e) => setQ(e.target.value)} />
        <button className="btn btn-primary" disabled={busy || selected.size === 0} onClick={bulkEnrich}>
          Обогатить ({selected.size})
        </button>
      </div>
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#0e1219] text-muted">
            <tr>
              <th className="text-left p-3 w-8"></th>
              <th className="text-left p-3">Имя</th>
              <th className="text-left p-3">Email</th>
              <th className="text-left p-3">Компания</th>
              <th className="text-left p-3">Должность</th>
              <th className="text-left p-3">Касаний</th>
              <th className="text-left p-3">AI-профиль</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((p: any) => (
              <tr key={p.id} className="border-t border-border hover:bg-[#1c2230]">
                <td className="p-3">
                  <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
                </td>
                <td className="p-3 font-medium cursor-pointer text-accent" onClick={() => setView({ name: 'person', id: p.id })}>
                  {p.full_name}
                </td>
                <td className="p-3 text-muted">{p.primary_email || '—'}</td>
                <td className="p-3">{p.company || '—'}</td>
                <td className="p-3">{p.title || '—'}</td>
                <td className="p-3">{p.interactions_count}</td>
                <td className="p-3">
                  {p.has_profile ? (
                    <span className="badge bg-[#0f2418] text-ok">conf {p.confidence?.toFixed(2)}</span>
                  ) : (
                    <span className="badge bg-[#1c2230] text-muted">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
