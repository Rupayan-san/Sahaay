import { Moon, Shield, Sun, UserCircle } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { getDefaultActorId, useAppStore } from '../../store/useAppStore';
import type { ActorRole } from '../../types';

const PAGE_TITLES: Record<string, string> = {
  '/dashboard': 'Priority Dashboard',
  '/input': 'Data Input',
  '/issues': 'Issue Board',
  '/extraction': 'Issue Extraction',
  '/matching': 'Volunteer Matching',
  '/assignments': 'Assignments',
};

function RoleButton({
  role,
  activeRole,
  onClick,
}: {
  role: ActorRole;
  activeRole: ActorRole;
  onClick: () => void;
}) {
  const active = role === activeRole;
  const Icon = role === 'admin' ? Shield : UserCircle;

  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition ${
        active
          ? 'bg-primary text-white'
          : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-low dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800'
      }`}
      type="button"
    >
      <Icon size={13} />
      {role === 'admin' ? 'Admin' : 'Volunteer'}
    </button>
  );
}

export function TopBar() {
  const location = useLocation();
  const { actorId, actorRole, isDarkMode, setActor, toggleDarkMode } = useAppStore();
  const pageTitle = PAGE_TITLES[location.pathname] ?? 'Sahaay';

  return (
    <header className="sticky top-0 z-30 border-b border-outline-variant bg-white/90 px-4 py-3 backdrop-blur dark:border-gray-800 dark:bg-gray-950/90 sm:px-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="font-heading text-xl font-bold text-on-surface dark:text-gray-100">{pageTitle}</h1>
          <p className="text-sm text-on-surface-variant dark:text-gray-400">
            Active actor: <span className="font-medium">{actorId.slice(0, 8)}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <RoleButton
            role="admin"
            activeRole={actorRole}
            onClick={() => setActor('admin', getDefaultActorId('admin'))}
          />
          <RoleButton
            role="volunteer"
            activeRole={actorRole}
            onClick={() => setActor('volunteer', getDefaultActorId('volunteer'))}
          />
          <button
            onClick={toggleDarkMode}
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-outline-variant text-on-surface-variant transition hover:bg-surface-container dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-900"
            aria-label="Toggle dark mode"
          >
            {isDarkMode ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </div>
    </header>
  );
}
