import type { IssueCategory } from '../../types';

interface CategoryBadgeProps {
  category: IssueCategory;
}

const CATEGORY_STYLES: Record<IssueCategory, string> = {
  water: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  medical: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400',
  food: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  infrastructure: 'bg-slate-100 text-slate-700 dark:bg-slate-800/50 dark:text-slate-400',
  sanitation: 'bg-lime-100 text-lime-700 dark:bg-lime-900/30 dark:text-lime-400',
  electricity: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  education: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  other: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
};

const CATEGORY_ICONS: Record<IssueCategory, string> = {
  water: 'water_drop',
  medical: 'local_hospital',
  food: 'restaurant',
  infrastructure: 'construction',
  sanitation: 'cleaning_services',
  electricity: 'bolt',
  education: 'school',
  other: 'category',
};

export function CategoryBadge({ category }: CategoryBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 label-caps ${CATEGORY_STYLES[category]}`}
    >
      <span className="material-symbols-outlined text-sm" style={{ fontSize: '14px' }}>
        {CATEGORY_ICONS[category]}
      </span>
      {category}
    </span>
  );
}
