import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

export function AppLayout() {
  return (
    <div className="min-h-screen bg-surface text-on-surface dark:bg-gray-950 dark:text-gray-100">
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main className="flex-1 px-4 py-5 pb-24 sm:px-6 lg:px-8 md:pb-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
