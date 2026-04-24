interface PriorityBadgeProps {
  score: number;
}

export function PriorityBadge({ score }: PriorityBadgeProps) {
  let label: string;
  let classes: string;

  if (score >= 70) {
    label = 'HIGH';
    classes = 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
  } else if (score >= 40) {
    label = 'MEDIUM';
    classes = 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400';
  } else {
    label = 'LOW';
    classes = 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400';
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 label-caps ${classes}`}
    >
      {label}
    </span>
  );
}
