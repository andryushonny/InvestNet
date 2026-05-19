import { useState } from 'react';
import { api, streamTask } from '../lib/api';

export default function Onboarding({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [provider, setProvider] = useState<'openrouter' | 'openai'>('openrouter');
  const [apiKey, setApiKey] = useState('');
  const [embeddingApiKey, setEmbeddingApiKey] = useState('');
  const [selfEmails, setSelfEmails] = useState('');
  const [mboxPath, setMboxPath] = useState<string | null>(null);
  const [linkedInPath, setLinkedInPath] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);

  const pushLog = (m: string) => setLog((l) => [...l.slice(-20), m]);

  async function saveKey() {
    setBusy(true);
    try {
      await api('/settings', {
        method: 'PUT',
        body: JSON.stringify({
          provider,
          api_key: apiKey,
          embedding_api_key: embeddingApiKey || apiKey,
          embedding_provider: 'openai',
          self_emails: selfEmails.split(/[\s,;]+/).map((s) => s.trim().toLowerCase()).filter(Boolean),
        }),
      });
      setStep(1);
    } catch (e: any) {
      alert('Ошибка: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function chooseMbox() {
    const p = await window.investnet?.openFile({ filters: [{ name: 'Mbox', extensions: ['mbox'] }] });
    if (p) setMboxPath(p);
  }
  async function chooseLinkedIn() {
    const p = await window.investnet?.openFile({ filters: [{ name: 'ZIP', extensions: ['zip'] }] });
    if (p) setLinkedInPath(p);
  }

  async function runImports() {
    setBusy(true);
    setLog([]);
    try {
      if (mboxPath) {
        pushLog('Импорт Gmail…');
        const { task_id } = await api<any>('/import/gmail', { method: 'POST', body: JSON.stringify({ path: mboxPath }) });
        await streamTask(task_id, (ev) => {
          if (ev.progress) pushLog(`Gmail: ${Math.round(ev.progress * 100)}%`);
          if (ev.done) pushLog('Gmail: готово');
          if (ev.failed) pushLog('Gmail: ошибка — ' + ev.error);
        });
      }
      if (linkedInPath) {
        pushLog('Импорт LinkedIn…');
        const { task_id } = await api<any>('/import/linkedin', { method: 'POST', body: JSON.stringify({ path: linkedInPath }) });
        await streamTask(task_id, (ev) => {
          if (ev.progress) pushLog(`LinkedIn: ${Math.round(ev.progress * 100)}%`);
          if (ev.done) pushLog('LinkedIn: готово');
          if (ev.failed) pushLog('LinkedIn: ошибка — ' + ev.error);
        });
      }
      pushLog('Индексация переписки (embeddings)…');
      const { task_id: rid } = await api<any>('/index/reindex', { method: 'POST' });
      await streamTask(rid, (ev) => {
        if (ev.progress) pushLog(`Index: ${Math.round(ev.progress * 100)}%`);
        if (ev.done) pushLog('Индексация: готово');
        if (ev.failed) pushLog('Индексация: ошибка — ' + ev.error);
      });
      onDone();
    } catch (e: any) {
      alert('Ошибка: ' + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-10 space-y-6">
      <h1 className="text-2xl font-bold">Добро пожаловать в InvestNet</h1>
      {step === 0 && (
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">1. Провайдер ИИ</h2>
          <div className="flex gap-3">
            <label className="flex items-center gap-2">
              <input type="radio" checked={provider === 'openrouter'} onChange={() => setProvider('openrouter')} />
              OpenRouter (рекомендовано)
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" checked={provider === 'openai'} onChange={() => setProvider('openai')} />
              OpenAI
            </label>
          </div>
          <div>
            <label className="text-sm text-muted">API-ключ {provider === 'openrouter' ? '(openrouter.ai/keys)' : '(platform.openai.com)'}</label>
            <input className="input" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div>
            <label className="text-sm text-muted">OpenAI API-ключ для embeddings (если используете OpenRouter, оставьте пустым — попробуем тот же ключ)</label>
            <input className="input" value={embeddingApiKey} onChange={(e) => setEmbeddingApiKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div>
            <label className="text-sm text-muted">Ваши email-адреса (через запятую) — нужны для определения «исходящих» писем</label>
            <input className="input" value={selfEmails} onChange={(e) => setSelfEmails(e.target.value)} placeholder="you@gmail.com, you@company.com" />
          </div>
          <button disabled={!apiKey || busy} onClick={saveKey} className="btn btn-primary">Далее</button>
        </div>
      )}
      {step === 1 && (
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold">2. Импорт данных</h2>
          <p className="text-sm text-muted">
            Заранее скачайте архивы: Gmail — на <a className="text-accent" href="#" onClick={(e) => { e.preventDefault(); window.investnet?.openExternal('https://takeout.google.com'); }}>takeout.google.com</a> (Mail в mbox).<br />
            LinkedIn — Settings → Data Privacy → Get a copy of your data (поставьте галочку Messages).
          </p>
          <div className="flex items-center gap-2">
            <button onClick={chooseMbox} className="btn">Выбрать .mbox</button>
            <span className="text-muted text-xs">{mboxPath || 'не выбрано'}</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={chooseLinkedIn} className="btn">Выбрать LinkedIn .zip</button>
            <span className="text-muted text-xs">{linkedInPath || 'не выбрано'}</span>
          </div>
          {log.length > 0 && (
            <pre className="bg-[#0e1219] border border-border rounded p-3 text-xs text-muted whitespace-pre-wrap max-h-64 overflow-auto">
              {log.join('\n')}
            </pre>
          )}
          <div className="flex gap-2">
            <button disabled={busy || (!mboxPath && !linkedInPath)} onClick={runImports} className="btn btn-primary">
              Импортировать и проиндексировать
            </button>
            <button disabled={busy} onClick={onDone} className="btn">Пропустить</button>
          </div>
        </div>
      )}
    </div>
  );
}
