import { ClipboardList, LayoutDashboard, List, Plus, Users } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { label: 'Input', icon: Plus, path: '/input' },
  { label: 'Issues', icon: List, path: '/issues' },
  { label: 'Matching', icon: Users, path: '/matching' },
  { label: 'Assignments', icon: ClipboardList, path: '/assignments' },
] as const;

export function Sidebar() {
  return (
    <>
      <aside className="hidden md:flex w-72 shrink-0 flex-col border-r border-outline-variant bg-primary text-white">
        <div className="border-b border-white/10 px-6 py-7">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal text-lg font-bold text-white">
              S
            </div>
            <div>
              <p className="font-heading text-xl font-bold tracking-tight">Sahaay</p>
              <p className="text-sm text-white/70">Community coordination hub</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-4 py-5">
          {NAV_ITEMS.map(({ label, icon: Icon, path }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition ${
                  isActive
                    ? 'bg-white/12 text-white shadow-sm'
                    : 'text-white/70 hover:bg-white/8 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-outline-variant bg-white/95 px-2 py-2 backdrop-blur dark:border-gray-800 dark:bg-gray-950/95 md:hidden">
        <div className="flex items-center gap-1 overflow-x-auto">
          {NAV_ITEMS.map(({ label, icon: Icon, path }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex min-w-[68px] flex-1 flex-col items-center justify-center rounded-2xl px-2 py-2 text-[11px] font-medium transition ${
                  isActive
                    ? 'bg-primary text-white'
                    : 'text-on-surface-variant hover:bg-surface-container dark:text-gray-400 dark:hover:bg-gray-900'
                }`
              }
            >
              <Icon size={16} />
              <span className="mt-1 truncate">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </>
  );
}
