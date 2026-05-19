import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const r = await api<any[]>('/tasks?limit=100');
        if (alive) setTasks(r);
      } catch {}
    }
    tick();
    const id = setInterval(tick, 1500);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Фоновые задачи</h1>
      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[#0e1219] text-muted">
            <tr>
              <th className="p-3 text-left">ID</th>
              <th className="p-3 text-left">Тип</th>
              <th className="p-3 text-left">Статус</th>
              <th className="p-3 text-left">Прогресс</th>
              <th className="p-3 text-left">Сообщение</th>
              <th className="p-3 text-left">Ошибка</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="p-3">{t.id}</td>
                <td className="p-3">{t.kind}</td>
                <td className="p-3">
                  <span className={`badge ${t.status === 'done' ? 'bg-[#0f2418] text-ok' : t.status === 'failed' ? 'bg-[#2a1313] text-err' : t.status === 'running' ? 'bg-[#1c2230] text-accent' : 'bg-[#1c2230] text-muted'}`}>
                    {t.status}
                  </span>
                </td>
                <td className="p-3">{Math.round((t.progress || 0) * 100)}%</td>
                <td className="p-3 text-muted text-xs max-w-md truncate">{t.message || ''}</td>
                <td className="p-3 text-err text-xs">{t.error || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
