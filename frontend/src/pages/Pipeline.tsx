import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { View } from '../App';

const STATUSES = ['new', 'researched', 'contacted', 'replied', 'meeting_scheduled', 'in_diligence', 'negotiating', 'won', 'lost'];

export default function Pipeline({ caseId, setView }: { caseId: number; setView: (v: View) => void }) {
  const [deals, setDeals] = useState<any[]>([]);

  async function reload() { setDeals(await api(`/cases/${caseId}/deals`)); }
  useEffect(() => { reload().catch(() => {}); }, [caseId]);

  async function changeStatus(dealId: number, status: string) {
    await api(`/deals/${dealId}`, { method: 'PATCH', body: JSON.stringify({ status }) });
    reload();
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <button className="text-muted text-sm" onClick={() => setView({ name: 'case', id: caseId })}>← К кейсу</button>
      <h1 className="text-2xl font-bold">Воронка</h1>
      <div className="flex gap-3 overflow-x-auto pb-4 flex-1">
        {STATUSES.map((status) => {
          const col = deals.filter((d) => d.status === status);
          return (
            <div key={status} className="min-w-[260px] flex-shrink-0">
              <div className="text-xs uppercase text-muted mb-2 flex justify-between">
                <span>{status}</span>
                <span>{col.length}</span>
              </div>
              <div
                className="bg-[#0e1219] border border-border rounded p-2 min-h-[400px] space-y-2"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = Number(e.dataTransfer.getData('text/plain'));
                  if (id) changeStatus(id, status);
                }}
              >
                {col.map((d) => (
                  <div
                    key={d.id}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/plain', String(d.id))}
                    className="card p-2 cursor-grab text-xs"
                    onClick={() => setView({ name: 'person', id: d.person_id })}
                  >
                    <div className="font-semibold text-sm">{d.person?.full_name}</div>
                    <div className="text-muted">{d.person?.company || '—'}</div>
                    <div className="mt-1 text-accent">Score {d.score?.toFixed(0)}</div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
