import { useEffect, useState } from 'react';
import { api, streamTask } from '../lib/api';
import type { View } from '../App';

export default function CaseDetail({ id, setView }: { id: number; setView: (v: View) => void }) {
  const [c, setC] = useState<any>(null);
  const [deals, setDeals] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);

  async function reload() {
    const [caseData, dealsData] = await Promise.all([api(`/cases/${id}`), api(`/cases/${id}/deals`)]);
    setC(caseData);
    setDeals(dealsData as any[]);
  }
  useEffect(() => { reload().catch(() => {}); }, [id]);

  async function rank() {
    setBusy(true);
    setProgress(0);
    try {
      const { task_id } = await api<any>(`/cases/${id}/rank`, { method: 'POST' });
      await streamTask(task_id, (ev) => {
        if (ev.progress) setProgress(ev.progress);
      });
      reload();
    } finally {
      setBusy(false);
      setProgress(0);
    }
  }

  if (!c) return <div className="text-muted">Загрузка…</div>;

  return (
    <div className="space-y-4">
      <button className="text-muted text-sm" onClick={() => setView({ name: 'cases' })}>← Кейсы</button>
      <div className="card">
        <h1 className="text-2xl font-bold">{c.title}</h1>
        <div className="flex flex-wrap gap-2 mt-2">
          {c.stage && <span className="badge bg-[#1c2230]">{c.stage}</span>}
          {c.sector && <span className="badge bg-[#1c2230]">{c.sector}</span>}
          {c.geography && <span className="badge bg-[#1c2230]">{c.geography}</span>}
          {c.ticket_range && <span className="badge bg-[#1c2230]">{c.ticket_range}</span>}
        </div>
        <p className="mt-3 text-muted whitespace-pre-wrap">{c.description}</p>
        <div className="flex gap-2 mt-4">
          <button className="btn btn-primary" disabled={busy} onClick={rank}>
            {busy ? `Ранжирую… ${Math.round(progress * 100)}%` : 'Ранжировать контакты'}
          </button>
          <button className="btn" onClick={() => setView({ name: 'pipeline', caseId: id })}>
            Воронка (kanban)
          </button>
        </div>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-border font-semibold">Топ контактов по скору ({deals.length})</div>
        <table className="w-full text-sm">
          <thead className="bg-[#0e1219] text-muted">
            <tr>
              <th className="text-left p-3">Score</th>
              <th className="text-left p-3">Имя</th>
              <th className="text-left p-3">Компания</th>
              <th className="text-left p-3">Угол</th>
              <th className="text-left p-3">Статус</th>
              <th className="text-left p-3"></th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d: any) => (
              <tr key={d.id} className="border-t border-border">
                <td className="p-3 font-bold">{d.score?.toFixed(0)}</td>
                <td className="p-3 cursor-pointer text-accent" onClick={() => setView({ name: 'person', id: d.person_id })}>
                  {d.person?.full_name}
                </td>
                <td className="p-3">{d.person?.company || '—'}</td>
                <td className="p-3 text-muted text-xs">{d.reasoning_json?.recommended_angle || ''}</td>
                <td className="p-3"><span className="badge bg-[#1c2230]">{d.status}</span></td>
                <td className="p-3 text-right">
                  <DraftButton dealId={d.id} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DraftButton({ dealId }: { dealId: number }) {
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<any>(null);

  async function go() {
    setBusy(true);
    try {
      const { task_id } = await api<any>(`/deals/${dealId}/draft-email`, { method: 'POST' });
      await streamTask(task_id, (ev) => {
        if (ev.result) setDraft(ev.result);
        if (ev.message) {
          try { setDraft(JSON.parse(ev.message)); } catch {}
        }
      });
    } finally { setBusy(false); }
  }

  if (draft) {
    return (
      <button className="text-accent text-sm" onClick={() => {
        const blob = `${draft.subject}\n\n${draft.body}`;
        navigator.clipboard.writeText(blob);
        alert('Скопировано');
      }}>📋 Скопировать</button>
    );
  }
  return <button className="btn text-xs" disabled={busy} onClick={go}>{busy ? '…' : 'Письмо'}</button>;
}
