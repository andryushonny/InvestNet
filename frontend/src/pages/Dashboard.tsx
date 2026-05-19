import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { View } from '../App';

export default function Dashboard({ setView }: { setView: (v: View) => void }) {
  const [stats, setStats] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const [s, t] = await Promise.all([api('/dashboard'), api<any[]>('/tasks?limit=10')]);
        if (!alive) return;
        setStats(s);
        setTasks(t);
      } catch {}
    }
    tick();
    const id = setInterval(tick, 2000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!stats) return <div className="text-muted">Загрузка…</div>;

  const cards = [
    { label: 'Контактов', value: stats.persons, view: { name: 'contacts' as const } },
    { label: 'Кейсов', value: stats.cases, view: { name: 'cases' as const } },
    { label: 'Открытых сделок', value: stats.open_deals, view: { name: 'cases' as const } },
    { label: 'С AI-профилем', value: stats.enriched },
    { label: 'Писем в БД', value: stats.interactions },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Дашборд</h1>
      <div className="grid grid-cols-5 gap-4">
        {cards.map((c) => (
          <div
            key={c.label}
            onClick={() => c.view && setView(c.view)}
            className={`card ${c.view ? 'cursor-pointer hover:border-accent' : ''}`}
          >
            <div className="text-muted text-xs uppercase">{c.label}</div>
            <div className="text-3xl font-bold mt-1">{c.value}</div>
          </div>
        ))}
      </div>
      <div className="card">
        <h2 className="text-lg font-semibold mb-3">Последние задачи</h2>
        {tasks.length === 0 ? (
          <div className="text-muted text-sm">Нет задач.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr>
                <th className="text-left">ID</th><th className="text-left">Тип</th><th className="text-left">Статус</th><th className="text-left">Прогресс</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => (
                <tr key={t.id} className="border-t border-border">
                  <td className="py-1">{t.id}</td>
                  <td>{t.kind}</td>
                  <td>
                    <span className={`badge ${t.status === 'done' ? 'bg-[#0f2418] text-ok' : t.status === 'failed' ? 'bg-[#2a1313] text-err' : 'bg-[#1c2230] text-muted'}`}>{t.status}</span>
                  </td>
                  <td>{Math.round((t.progress || 0) * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
