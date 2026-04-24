import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, ChevronDown, ChevronUp, Filter } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getIssues } from '../api/issues';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { EmptyState } from '../components/ui/EmptyState';
import { PriorityBadge } from '../components/ui/PriorityBadge';
import type { Issue, IssueCategory, IssueStatus } from '../types';

type PriorityFilter = 'all' | 'high' | 'medium' | 'low';
type SortOption = 'priority_score' | 'created_at' | 'report_count';

function getPriorityLevel(issue: Issue): Exclude<PriorityFilter, 'all'> {
  if (issue.priority_score >= 70) {
    return 'high';
  }
  if (issue.priority_score >= 40) {
    return 'medium';
  }
  return 'low';
}

function IssueBoardSkeleton() {
  return (
    <div className="grid gap-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="card animate-pulse p-5">
          <div className="h-4 w-2/3 rounded-full bg-surface-container dark:bg-gray-800" />
          <div className="mt-4 h-3 w-1/3 rounded-full bg-surface-container dark:bg-gray-800" />
          <div className="mt-6 space-y-2">
            <div className="h-3 rounded-full bg-surface-container dark:bg-gray-800" />
            <div className="h-3 rounded-full bg-surface-container dark:bg-gray-800" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function IssueBoard() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<IssueStatus | 'all'>('all');
  const [categoryFilter, setCategoryFilter] = useState<IssueCategory | 'all'>('all');
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>('all');
  const [sortBy, setSortBy] = useState<SortOption>('priority_score');
  const [expandedIssueId, setExpandedIssueId] = useState<string | null>(null);

  const issuesQuery = useQuery({
    queryKey: ['issues', statusFilter, categoryFilter],
    queryFn: async () =>
      getIssues({
        limit: 50,
        skip: 0,
        status: statusFilter === 'all' ? undefined : statusFilter,
        category: categoryFilter === 'all' ? undefined : categoryFilter,
      }),
    refetchInterval: 30_000,
  });

  const issues = useMemo(() => {
    const rawIssues = issuesQuery.data?.data ?? [];
    const filtered = rawIssues.filter((issue) => {
      if (priorityFilter === 'all') {
        return true;
      }
      return getPriorityLevel(issue) === priorityFilter;
    });

    return [...filtered].sort((left, right) => {
      if (sortBy === 'created_at') {
        return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
      }
      if (sortBy === 'report_count') {
        return right.report_count - left.report_count;
      }
      return right.priority_score - left.priority_score;
    });
  }, [issuesQuery.data?.data, priorityFilter, sortBy]);

  return (
    <div className="space-y-6">
      <section className="rounded-[32px] bg-gradient-to-r from-surface-container to-white px-6 py-7 shadow-sm dark:from-gray-900 dark:to-gray-950 sm:px-8">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="label-caps text-on-surface-variant dark:text-gray-500">Issue board</p>
            <h2 className="mt-3 font-heading text-3xl font-bold tracking-tight text-on-surface dark:text-white">
              Track active issues across the platform.
            </h2>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm text-on-surface shadow-sm dark:bg-gray-900 dark:text-gray-200">
            <Filter size={15} />
            {issues.length} issue{issues.length === 1 ? '' : 's'} shown
          </div>
        </div>
      </section>

      <div className="card grid gap-4 p-5 lg:grid-cols-4">
        <label className="space-y-2 text-sm">
          <span className="label-caps text-on-surface-variant dark:text-gray-500">Status</span>
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as IssueStatus | 'all')}
            className="input-field"
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="assigned">Assigned</option>
            <option value="completed">Completed</option>
          </select>
        </label>

        <label className="space-y-2 text-sm">
          <span className="label-caps text-on-surface-variant dark:text-gray-500">Category</span>
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value as IssueCategory | 'all')}
            className="input-field"
          >
            <option value="all">All categories</option>
            <option value="water">Water</option>
            <option value="medical">Medical</option>
            <option value="food">Food</option>
            <option value="infrastructure">Infrastructure</option>
            <option value="sanitation">Sanitation</option>
            <option value="electricity">Electricity</option>
            <option value="education">Education</option>
            <option value="other">Other</option>
          </select>
        </label>

        <label className="space-y-2 text-sm">
          <span className="label-caps text-on-surface-variant dark:text-gray-500">Priority</span>
          <select
            value={priorityFilter}
            onChange={(event) => setPriorityFilter(event.target.value as PriorityFilter)}
            className="input-field"
          >
            <option value="all">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>

        <label className="space-y-2 text-sm">
          <span className="label-caps text-on-surface-variant dark:text-gray-500">Sort by</span>
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as SortOption)}
            className="input-field"
          >
            <option value="priority_score">Priority score</option>
            <option value="created_at">Created time</option>
            <option value="report_count">Report count</option>
          </select>
        </label>
      </div>

      {issuesQuery.isLoading ? <IssueBoardSkeleton /> : null}

      {!issuesQuery.isLoading && issues.length === 0 ? (
        <EmptyState
          title="No issues match these filters"
          message="Try changing the filters or submit a new report from the input screen."
        />
      ) : null}

      {!issuesQuery.isLoading ? (
        <div className="grid gap-4">
          {issues.map((issue) => {
            const expanded = expandedIssueId === issue.issue_id;

            return (
              <article
                key={issue.issue_id}
                className="card overflow-hidden"
              >
                <button
                  type="button"
                  className="w-full px-5 py-5 text-left transition hover:bg-surface-container-low dark:hover:bg-gray-900/60 sm:px-6"
                  onClick={() => setExpandedIssueId(expanded ? null : issue.issue_id)}
                >
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <CategoryBadge category={issue.category} />
                        <PriorityBadge score={issue.priority_score} />
                        <span className="rounded-full bg-surface-container px-3 py-1 text-xs font-semibold capitalize text-on-surface-variant dark:bg-gray-800 dark:text-gray-400">
                          {issue.status}
                        </span>
                      </div>
                      <div>
                        <h3 className="font-heading text-xl font-bold text-on-surface dark:text-white">{issue.title}</h3>
                        <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                          {issue.description.length > 140
                            ? `${issue.description.slice(0, 140)}...`
                            : issue.description}
                        </p>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-4">
                      <div className="text-right text-sm text-on-surface-variant dark:text-gray-400">
                        <p>{issue.location}</p>
                        <p>{issue.report_count} reports</p>
                      </div>
                      {expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </div>
                  </div>
                </button>

                {expanded ? (
                  <div className="border-t border-outline-variant bg-surface-container-low px-5 py-5 dark:border-gray-800 dark:bg-gray-950/70 sm:px-6">
                    <p className="text-sm leading-7 text-on-surface dark:text-gray-200">{issue.description}</p>
                    <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                      <button
                        type="button"
                        className="btn-primary inline-flex items-center justify-center gap-2"
                        onClick={() => navigate('/matching', { state: { issue } })}
                      >
                        Find Volunteers
                        <ArrowRight size={16} />
                      </button>
                      <button
                        type="button"
                        className="btn-outline inline-flex items-center justify-center gap-2"
                        onClick={() => navigate('/assignments', { state: { issue } })}
                      >
                        View Assignments
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
