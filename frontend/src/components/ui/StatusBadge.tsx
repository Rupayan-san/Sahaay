import type { AssignmentStatus } from '../../types';

interface StatusBadgeProps {
  status: AssignmentStatus;
}

const STATUS_STYLES: Record<AssignmentStatus, string> = {
  applied: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  assigned: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  in_progress: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  submitted: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  verified: 'bg-teal/10 text-teal dark:bg-teal/20 dark:text-teal',
  completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const STATUS_LABELS: Record<AssignmentStatus, string> = {
  applied: 'Applied',
  assigned: 'Assigned',
  in_progress: 'In Progress',
  submitted: 'Submitted',
  verified: 'Verified',
  completed: 'Completed',
  rejected: 'Rejected',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 label-caps ${STATUS_STYLES[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
