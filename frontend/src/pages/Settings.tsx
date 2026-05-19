import { useEffect, useState } from 'react';
import { api, streamTask } from '../lib/api';

export default function Settings() {
  const [s, setS] = useState<any>(null);
  const [apiKey, setApiKey] = useState('');
  const [embKey, setEmbKey] = useState('');
  const [emails, setEmails] = useState('');
  const [models, setModels] = useState<any>({});
  const [provider, setProvider] = useState<'openrouter' | 'openai'>('openrouter');
  const [savedMsg, setSavedMsg] = useState('');

  async function reload() {
    const r = await api<any>('/settings');
    setS(r);
    setProvider(r.provider);
    setEmails((r.self_emails || []).join(', '));
    setModels(r.models || {});
  }
  useEffect(() => { reload().catch(() => {}); }, []);

  async function save() {
    const payload: any = { provider, models };
    if (apiKey) payload.api_key = apiKey;
    if (embKey) payload.embedding_api_key = embKey;
    payload.self_emails = emails.split(/[,;\s]+/).map((x) => x.trim().toLowerCase()).filter(Boolean);
    await api('/settings', { method: 'PUT', body: JSON.stringify(payload) });
    setApiKey(''); setEmbKey('');
    setSavedMsg('Сохранено');
    setTimeout(() => setSavedMsg(''), 1500);
    reload();
  }

  async function reindex() {
    const { task_id } = await api<any>('/index/reindex', { method: 'POST' });
    await streamTask(task_id, () => {});
    alert('Переиндексация завершена');
  }

  if (!s) return <div className="text-muted">Загрузка…</div>;

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-bold">Настройки</h1>
      <div className="card space-y-3">
        <h2 className="font-semibold">Провайдер LLM</h2>
        <div className="flex gap-3">
          <label className="flex items-center gap-2"><input type="radio" checked={provider === 'openrouter'} onChange={() => setProvider('openrouter')} /> OpenRouter</label>
          <label className="flex items-center gap-2"><input type="radio" checked={provider === 'openai'} onChange={() => setProvider('openai')} /> OpenAI</label>
        </div>
        <div>
          <label className="text-sm text-muted">API-ключ (текущий: {s.api_key_masked || '—'})</label>
          <input className="input" type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="оставьте пустым, чтобы не менять" />
        </div>
        <div>
          <label className="text-sm text-muted">OpenAI ключ для embeddings (текущий: {s.embedding_api_key_masked || '—'})</label>
          <input className="input" type="password" value={embKey} onChange={(e) => setEmbKey(e.target.value)} />
        </div>
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Модели</h2>
        {(['embedding', 'enrichment', 'ranking', 'composer'] as const).map((k) => (
          <div key={k}>
            <label className="text-sm text-muted">{k}</label>
            <input className="input" value={models[k] || ''} onChange={(e) => setModels({ ...models, [k]: e.target.value })} />
          </div>
        ))}
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Ваши email-адреса</h2>
        <input className="input" value={emails} onChange={(e) => setEmails(e.target.value)} placeholder="you@gmail.com, you@company.com" />
      </div>

      <div className="card space-y-3">
        <h2 className="font-semibold">Индекс</h2>
        <button className="btn" onClick={reindex}>Перестроить индекс переписки</button>
      </div>

      <div className="flex items-center gap-3">
        <button className="btn btn-primary" onClick={save}>Сохранить</button>
        {savedMsg && <span className="text-ok text-sm">{savedMsg}</span>}
      </div>
    </div>
  );
}
