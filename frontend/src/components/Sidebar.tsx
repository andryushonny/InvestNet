import type { View } from '../App';

const items: { name: View['name']; label: string }[] = [
  { name: 'dashboard', label: 'Дашборд' },
  { name: 'contacts', label: 'Контакты' },
  { name: 'cases', label: 'Кейсы' },
  { name: 'tasks', label: 'Задачи' },
  { name: 'settings', label: 'Настройки' },
];

export default function Sidebar({ view, setView }: { view: View; setView: (v: View) => void }) {
  return (
    <aside className="w-56 bg-panel border-r border-border p-4 flex flex-col gap-1">
      <div className="text-lg font-semibold mb-4 text-accent">InvestNet</div>
      {items.map((it) => (
        <button
          key={it.name}
          onClick={() => setView({ name: it.name } as any)}
          className={`text-left px-3 py-2 rounded-md transition ${
            view.name === it.name || (it.name === 'cases' && (view.name === 'case' || view.name === 'pipeline'))
              ? 'bg-[#1c2230] text-white'
              : 'text-muted hover:bg-[#1c2230] hover:text-white'
          }`}
        >
          {it.label}
        </button>
      ))}
    </aside>
  );
}
