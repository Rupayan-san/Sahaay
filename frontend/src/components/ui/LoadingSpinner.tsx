import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
}

export function LoadingSpinner({ size = 32, message }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Loader2
        size={size}
        className="animate-spin text-secondary"
      />
      {message && (
        <p className="text-sm text-on-surface-variant dark:text-gray-400">{message}</p>
      )}
    </div>
  );
}
