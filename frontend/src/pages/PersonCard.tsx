import { useEffect, useState } from 'react';
import { api, streamTask } from '../lib/api';
import type { View } from '../App';

export default function PersonCard({ id, setView }: { id: number; setView: (v: View) => void }) {
  const [data, setData] = useState<any>(null);
  const [tab, setTab] = useState<'profile' | 'history' | 'deals' | 'drafts'>('profile');
  const [busy, setBusy] = useState(false);

  async function reload() {
    setData(await api(`/persons/${id}`));
  }
  useEffect(() => { reload().catch(() => {}); }, [id]);

  async function enrich() {
    setBusy(true);
    try {
      const { task_id } = await api<any>(`/persons/${id}/enrich`, { method: 'POST' });
      await streamTask(task_id, () => {});
      reload();
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <div className="text-muted">Загрузка…</div>;
  const { person, profile, interactions, deals, drafts } = data;

  const interests = profile?.investment_interests ? JSON.parse(profile.investment_interests) : [];
  const stages = profile?.stage_focus ? JSON.parse(profile.stage_focus) : [];
  const geos = profile?.geography ? JSON.parse(profile.geography) : [];

  return (
    <div className="space-y-4">
      <button className="text-muted text-sm" onClick={() => setView({ name: 'contacts' })}>← Назад</button>
      <div className="card flex items-start justify-between">
        <div>
          <div className="text-2xl font-bold">{person.full_name}</div>
          <div className="text-muted">{person.title || ''} {person.company ? `@ ${person.company}` : ''}</div>
          <div className="text-muted text-sm">{person.primary_email || ''}</div>
          {person.linkedin_url && (
            <button className="text-accent text-sm mt-1" onClick={() => window.investnet?.openExternal(person.linkedin_url)}>
              LinkedIn ↗
            </button>
          )}
        </div>
        <button className="btn btn-primary" disabled={busy} onClick={enrich}>
          {busy ? 'Обогащаю…' : profile ? 'Переобогатить' : 'Обогатить'}
        </button>
      </div>

      <div className="flex gap-2 border-b border-border">
        {(['profile', 'history', 'deals', 'drafts'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 ${tab === t ? 'border-b-2 border-accent text-white' : 'text-muted'}`}>
            {t === 'profile' ? 'Профиль' : t === 'history' ? `История (${interactions.length})` : t === 'deals' ? `Сделки (${deals.length})` : `Черновики (${drafts.length})`}
          </button>
        ))}
      </div>

      {tab === 'profile' && (
        <div className="card space-y-3">
          {!profile ? (
            <div className="text-muted">AI-профиль ещё не построен. Нажмите «Обогатить».</div>
          ) : (
            <>
              <div className="text-sm text-muted">AI-резюме (confidence {profile.confidence?.toFixed(2)})</div>
              <div>{profile.ai_summary}</div>
              <div className="flex flex-wrap gap-2 pt-2">
                {interests.map((i: string) => <span key={i} className="badge bg-[#1c2230] text-accent">{i}</span>)}
              </div>
              <div className="grid grid-cols-3 gap-3 pt-2 text-sm">
                <div><div className="text-muted text-xs">Чек</div>{profile.preferred_ticket || '—'}</div>
                <div><div className="text-muted text-xs">Стадии</div>{stages.join(', ') || '—'}</div>
                <div><div className="text-muted text-xs">География</div>{geos.join(', ') || '—'}</div>
              </div>
            </>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="space-y-2">
          {interactions.length === 0 ? <div className="text-muted">Касаний нет.</div> : interactions.map((i: any) => (
            <div key={i.id} className="card">
              <div className="flex justify-between text-xs text-muted">
                <span>{i.direction === 'incoming' ? '← incoming' : '→ outgoing'} · {i.channel}</span>
                <span>{i.occurred_at?.slice(0, 16).replace('T', ' ')}</span>
              </div>
              <div className="font-medium mt-1">{i.subject || '(без темы)'}</div>
              <div className="text-sm text-muted whitespace-pre-wrap mt-1 line-clamp-6">{i.body_cleaned}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'deals' && (
        <div className="space-y-2">
          {deals.length === 0 ? <div className="text-muted">Нет сделок.</div> : deals.map((d: any) => (
            <div key={d.id} className="card flex items-center justify-between">
              <div>
                <div className="font-medium">Кейс #{d.case_id}</div>
                <div className="text-xs text-muted">Статус: {d.status} · Score: {d.score?.toFixed(1)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'drafts' && (
        <div className="space-y-2">
          {drafts.length === 0 ? <div className="text-muted">Черновиков нет.</div> : drafts.map((d: any) => (
            <div key={d.id} className="card">
              <div className="font-medium">{d.subject}</div>
              <div className="whitespace-pre-wrap text-sm mt-2">{d.body}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
