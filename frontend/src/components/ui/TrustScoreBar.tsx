interface TrustScoreBarProps {
  score: number;
  showLabel?: boolean;
}

export function TrustScoreBar({ score, showLabel = true }: TrustScoreBarProps) {
  let barColor: string;

  if (score >= 80) {
    barColor = 'bg-teal';
  } else if (score >= 60) {
    barColor = 'bg-indigo-500';
  } else {
    barColor = 'bg-yellow-500';
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-surface-container dark:bg-gray-800 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${barColor}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs font-semibold text-on-surface-variant dark:text-gray-400 tabular-nums min-w-[2.5rem] text-right">
          {score.toFixed(1)}
        </span>
      )}
    </div>
  );
}
