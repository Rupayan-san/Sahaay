import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  message?: string;
  icon?: React.ReactNode;
}

export function EmptyState({
  title = 'No data found',
  message = 'There is nothing to display here yet.',
  icon,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="rounded-2xl bg-surface-container dark:bg-gray-800 p-5">
        {icon ?? <Inbox size={40} className="text-outline dark:text-gray-500" />}
      </div>
      <div>
        <h3 className="font-heading text-lg font-semibold text-on-surface dark:text-gray-200">
          {title}
        </h3>
        <p className="mt-1 text-sm text-on-surface-variant dark:text-gray-400 max-w-xs">
          {message}
        </p>
      </div>
    </div>
  );
}
