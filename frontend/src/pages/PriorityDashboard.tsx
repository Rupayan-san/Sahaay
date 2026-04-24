import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  ArrowRight,
  ClipboardList,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getIssues } from '../api/issues';
import { getLeaderboard } from '../api/leaderboard';
import { getDashboardStats } from '../api/reports';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { PriorityBadge } from '../components/ui/PriorityBadge';
import { TrustScoreBar } from '../components/ui/TrustScoreBar';
import type { Issue, LeaderboardEntry } from '../types';

function formatRelativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  const diffHours = Math.max(0, Math.floor((Date.now() - timestamp) / (1000 * 60 * 60)));

  if (diffHours < 1) {
    return 'less than 1 hour ago';
  }
  if (diffHours < 24) {
    return `${diffHours}h ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function StatsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="card animate-pulse p-5">
          <div className="h-10 w-10 rounded-2xl bg-surface-container dark:bg-gray-800" />
          <div className="mt-5 h-8 w-20 rounded-full bg-surface-container dark:bg-gray-800" />
          <div className="mt-3 h-3 w-28 rounded-full bg-surface-container dark:bg-gray-800" />
        </div>
      ))}
    </div>
  );
}

function PanelSkeleton() {
  return (
    <div className="card animate-pulse p-6">
      <div className="h-5 w-40 rounded-full bg-surface-container dark:bg-gray-800" />
      <div className="mt-6 space-y-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="space-y-2">
            <div className="h-4 w-2/3 rounded-full bg-surface-container dark:bg-gray-800" />
            <div className="h-3 w-full rounded-full bg-surface-container dark:bg-gray-800" />
          </div>
        ))}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  helper,
  icon,
  tone,
  bar,
}: {
  label: string;
  value: string | number;
  helper: string;
  icon: React.ReactNode;
  tone: string;
  bar?: React.ReactNode;
}) {
  return (
    <article className="card p-5">
      <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${tone}`}>{icon}</div>
      <p className="mt-5 text-3xl font-heading font-bold text-on-surface dark:text-white">{value}</p>
      <p className="mt-2 text-sm font-medium text-on-surface dark:text-gray-200">{label}</p>
      <p className="mt-1 text-xs text-on-surface-variant dark:text-gray-500">{helper}</p>
      {bar ? <div className="mt-4">{bar}</div> : null}
    </article>
  );
}

function HighPriorityList({ issues }: { issues: Issue[] }) {
  const navigate = useNavigate();

  if (issues.length === 0) {
    return (
      <EmptyState
        title="No high-priority issues right now"
        message="The open queue is under control at the moment."
      />
    );
  }

  return (
    <div className="space-y-3">
      {issues.map((issue) => (
        <button
          key={issue.issue_id}
          type="button"
          onClick={() => navigate('/matching', { state: { issue } })}
          className="w-full rounded-[24px] border border-outline-variant bg-surface-container-low p-4 text-left transition hover:border-primary/40 hover:bg-white dark:border-gray-800 dark:bg-gray-950/60 dark:hover:bg-gray-900"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <CategoryBadge category={issue.category} />
                <PriorityBadge score={issue.priority_score} />
              </div>
              <h3 className="mt-3 text-lg font-semibold text-on-surface dark:text-white">{issue.title}</h3>
              <p className="mt-1 text-sm text-on-surface-variant dark:text-gray-400">{issue.location}</p>
            </div>
            <div className="shrink-0 text-sm text-on-surface-variant dark:text-gray-400">
              <p>{issue.report_count} reports</p>
              <p>{formatRelativeTime(issue.created_at)}</p>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

function LeaderboardList({ entries }: { entries: LeaderboardEntry[] }) {
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No leaderboard data yet"
        message="Volunteer rankings will appear as tasks are completed."
      />
    );
  }

  return (
    <div className="space-y-4">
      {entries.map((entry) => (
        <div
          key={entry.volunteer_id}
          className="rounded-[24px] border border-outline-variant bg-surface-container-low p-4 dark:border-gray-800 dark:bg-gray-950/60"
        >
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-secondary/10 text-sm font-bold text-secondary">
              #{entry.rank}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-on-surface dark:text-white">{entry.name}</p>
                  <p className="mt-1 text-xs text-on-surface-variant dark:text-gray-400">
                    {entry.tasks_completed} tasks completed
                  </p>
                </div>
                <p className="text-sm font-semibold text-teal">{entry.points} pts</p>
              </div>
              <div className="mt-3">
                <TrustScoreBar score={entry.trust_score} />
              </div>
              {entry.badges.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {entry.badges.slice(0, 3).map((badge) => (
                    <span
                      key={badge}
                      className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary/20 dark:text-primary-200"
                    >
                      {badge}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function PriorityDashboard() {
  const navigate = useNavigate();
  const statsQuery = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    refetchInterval: 60_000,
  });

  const issuesQuery = useQuery({
    queryKey: ['issues', 'dashboard', 'open'],
    queryFn: async () => getIssues({ limit: 50, skip: 0, status: 'open' }),
    refetchInterval: 60_000,
  });

  const leaderboardQuery = useQuery({
    queryKey: ['leaderboard', 'points', 'all_time', 5],
    queryFn: async () => getLeaderboard({ category: 'points', timeframe: 'all_time', limit: 5 }),
    refetchInterval: 60_000,
  });

  const highPriorityIssues = useMemo(() => {
    return (issuesQuery.data?.data ?? [])
      .filter((issue) => issue.priority_score >= 70)
      .sort((left, right) => right.priority_score - left.priority_score);
  }, [issuesQuery.data?.data]);

  const stats = statsQuery.data;
  const leaderboard = leaderboardQuery.data?.leaderboard ?? [];
  const showInitialLoading =
    statsQuery.isPending && issuesQuery.isPending && leaderboardQuery.isPending;

  if (showInitialLoading) {
    return (
      <div className="space-y-6">
        <section className="rounded-[32px] bg-gradient-to-r from-primary to-slate-900 px-6 py-8 text-white shadow-xl sm:px-8">
          <p className="label-caps text-white/70">Operations overview</p>
          <h2 className="mt-3 font-heading text-3xl font-bold tracking-tight sm:text-4xl">
            Live priority visibility across the platform.
          </h2>
        </section>
        <StatsSkeleton />
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <PanelSkeleton />
          <PanelSkeleton />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] bg-gradient-to-r from-primary to-slate-900 px-6 py-8 text-white shadow-xl sm:px-8">
        <p className="label-caps text-white/70">Operations overview</p>
        <h2 className="mt-3 font-heading text-3xl font-bold tracking-tight sm:text-4xl">
          Watch the highest-risk issues and volunteer momentum in one view.
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-white/80 sm:text-base">
          This dashboard refreshes every minute so admins can move quickly on urgent work and spot gaps in response capacity.
        </p>
      </section>

      {stats ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Active Issues"
            value={stats.active_issues}
            helper={
              stats.high_priority_open > 0
                ? `${stats.high_priority_open} high-priority issue(s) need attention`
                : 'No high-priority open issues'
            }
            tone={
              stats.high_priority_open > 0
                ? 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-300'
                : 'bg-surface-container text-on-surface dark:bg-gray-800 dark:text-gray-100'
            }
            icon={<AlertTriangle size={20} />}
          />
          <StatCard
            label="Pending Assignments"
            value={stats.pending_assignments}
            helper="Volunteer applications waiting for action"
            tone="bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-300"
            icon={<ClipboardList size={20} />}
          />
          <StatCard
            label="Active Volunteers"
            value={stats.volunteers_active}
            helper="Currently available volunteers in the system"
            tone="bg-sky-50 text-sky-600 dark:bg-sky-950/30 dark:text-sky-300"
            icon={<Users size={20} />}
          />
          <StatCard
            label="Avg Trust Score"
            value={stats.avg_trust_score.toFixed(1)}
            helper="Average trust across active volunteers"
            tone="bg-teal/10 text-teal dark:bg-teal/20 dark:text-teal"
            icon={<ShieldCheck size={20} />}
            bar={<TrustScoreBar score={stats.avg_trust_score} showLabel={false} />}
          />
        </div>
      ) : (
        <StatsSkeleton />
      )}

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <section className="card p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="label-caps text-on-surface-variant dark:text-gray-500">Priority queue</p>
              <h3 className="mt-2 text-xl font-bold text-on-surface dark:text-white">High-priority open issues</h3>
            </div>
            <button
              type="button"
              className="btn-outline inline-flex items-center gap-2"
              onClick={() => navigate('/issues')}
            >
              Issue board
              <ArrowRight size={16} />
            </button>
          </div>

          <div className="mt-6">
            {issuesQuery.isPending ? (
              <LoadingSpinner message="Loading issue priorities..." />
            ) : (
              <HighPriorityList issues={highPriorityIssues} />
            )}
          </div>
        </section>

        <section className="card p-6">
          <p className="label-caps text-on-surface-variant dark:text-gray-500">Volunteer momentum</p>
          <h3 className="mt-2 text-xl font-bold text-on-surface dark:text-white">Top 5 by points</h3>
          <div className="mt-6">
            {leaderboardQuery.isPending ? (
              <LoadingSpinner message="Loading leaderboard..." />
            ) : (
              <LeaderboardList entries={leaderboard} />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
