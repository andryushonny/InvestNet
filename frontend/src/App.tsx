import { useEffect, useState } from 'react';
import { api } from './lib/api';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Contacts from './pages/Contacts';
import PersonCard from './pages/PersonCard';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import Pipeline from './pages/Pipeline';
import Settings from './pages/Settings';
import Onboarding from './pages/Onboarding';
import Tasks from './pages/Tasks';

export type View =
  | { name: 'dashboard' }
  | { name: 'contacts' }
  | { name: 'person'; id: number }
  | { name: 'cases' }
  | { name: 'case'; id: number }
  | { name: 'pipeline'; caseId: number }
  | { name: 'settings' }
  | { name: 'tasks' };

export default function App() {
  const [ready, setReady] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [view, setView] = useState<View>({ name: 'dashboard' });

  useEffect(() => {
    (async () => {
      try {
        await api('/healthz');
        const s = await api<any>('/settings');
        if (!s.api_key_masked) setNeedsOnboarding(true);
        setReady(true);
      } catch (e) {
        console.error(e);
        setTimeout(() => location.reload(), 1500);
      }
    })();
  }, []);

  if (!ready) {
    return (
      <div className="flex h-full items-center justify-center text-muted">
        Запуск InvestNet…
      </div>
    );
  }

  if (needsOnboarding) {
    return <Onboarding onDone={() => setNeedsOnboarding(false)} />;
  }

  return (
    <div className="flex h-full">
      <Sidebar view={view} setView={setView} />
      <main className="flex-1 overflow-auto p-6">
        {view.name === 'dashboard' && <Dashboard setView={setView} />}
        {view.name === 'contacts' && <Contacts setView={setView} />}
        {view.name === 'person' && <PersonCard id={view.id} setView={setView} />}
        {view.name === 'cases' && <Cases setView={setView} />}
        {view.name === 'case' && <CaseDetail id={view.id} setView={setView} />}
        {view.name === 'pipeline' && <Pipeline caseId={view.caseId} setView={setView} />}
        {view.name === 'settings' && <Settings />}
        {view.name === 'tasks' && <Tasks />}
      </main>
    </div>
  );
}
