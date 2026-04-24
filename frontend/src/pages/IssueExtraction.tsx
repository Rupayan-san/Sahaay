import { ArrowRight, CheckCircle2, Layers3, MapPin, ShieldAlert, Sparkles } from 'lucide-react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { CategoryBadge } from '../components/ui/CategoryBadge';
import { PriorityBadge } from '../components/ui/PriorityBadge';
import { useAppStore } from '../store/useAppStore';
import type { Issue } from '../types';

interface ExtractionLocationState {
  issue?: Issue;
  matched_existing?: boolean;
}

const revealDelays = ['0ms', '80ms', '160ms', '240ms', '320ms'];

export function IssueExtraction() {
  const navigate = useNavigate();
  const location = useLocation();
  const { lastExtractedIssue } = useAppStore();
  const state = (location.state ?? {}) as ExtractionLocationState;
  const issue = state.issue ?? lastExtractedIssue;
  const matchedExisting = Boolean(state.matched_existing);

  if (!issue) {
    return <Navigate to="/input" replace />;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <section className="rounded-[32px] bg-gradient-to-br from-primary via-primary-container to-slate-900 px-6 py-8 text-white shadow-xl sm:px-8">
        <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-medium text-white/90">
          <Sparkles size={16} />
          AI issue extraction complete
        </div>
        <h2 className="mt-4 font-heading text-3xl font-bold tracking-tight sm:text-4xl">{issue.title}</h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-white/80 sm:text-base">{issue.description}</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          {[
            {
              title: 'Category',
              body: <CategoryBadge category={issue.category} />,
              icon: <Layers3 size={18} className="text-primary" />,
            },
            {
              title: 'Location',
              body: <span className="text-base font-semibold text-on-surface dark:text-gray-100">{issue.location}</span>,
              icon: <MapPin size={18} className="text-primary" />,
            },
            {
              title: 'Severity',
              body: (
                <span className="inline-flex rounded-full bg-red-50 px-3 py-1 text-sm font-semibold capitalize text-red-600 dark:bg-red-950/30 dark:text-red-300">
                  {issue.severity}
                </span>
              ),
              icon: <ShieldAlert size={18} className="text-primary" />,
            },
            {
              title: 'Description',
              body: <p className="text-sm leading-7 text-on-surface dark:text-gray-200">{issue.description}</p>,
              icon: <CheckCircle2 size={18} className="text-primary" />,
            },
          ].map((item, index) => (
            <article
              key={item.title}
              className="fade-reveal card p-5"
              style={{ animationDelay: revealDelays[index] }}
            >
              <div className="mb-3 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary/10 dark:bg-primary/20">
                  {item.icon}
                </div>
                <p className="label-caps text-on-surface-variant dark:text-gray-500">{item.title}</p>
              </div>
              {item.body}
            </article>
          ))}
        </div>

        <aside className="space-y-4">
          <div className="fade-reveal card p-6" style={{ animationDelay: revealDelays[4] }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="label-caps text-on-surface-variant dark:text-gray-500">Priority score</p>
                <p className="mt-2 text-4xl font-heading font-bold text-on-surface dark:text-white">
                  {issue.priority_score}
                </p>
              </div>
              <PriorityBadge score={issue.priority_score} />
            </div>
            <div className="mt-5 h-3 overflow-hidden rounded-full bg-surface-container dark:bg-gray-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-teal to-primary"
                style={{ width: `${Math.min(100, issue.priority_score)}%` }}
              />
            </div>
          </div>

          <div className="card p-6">
            <p className="label-caps text-on-surface-variant dark:text-gray-500">Aggregation status</p>
            <div className="mt-4 rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70">
              {matchedExisting ? (
                <>
                  <p className="text-base font-semibold text-on-surface dark:text-gray-100">Matched an existing issue</p>
                  <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                    This report increased the visibility of an existing issue. The issue now reflects{' '}
                    <span className="font-semibold text-on-surface dark:text-gray-200">{issue.report_count}</span>{' '}
                    reports in total.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-base font-semibold text-on-surface dark:text-gray-100">Created a new issue</p>
                  <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                    The report created a new issue record and is ready for volunteer matching.
                  </p>
                </>
              )}
            </div>
          </div>

          <div className="card space-y-3 p-6">
            <button
              type="button"
              className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
              onClick={() => navigate('/matching', { state: { issue } })}
            >
              Find Volunteers
              <ArrowRight size={16} />
            </button>
            <button
              type="button"
              className="btn-outline inline-flex w-full items-center justify-center gap-2 py-3"
              onClick={() => navigate('/issues')}
            >
              View Issue Board
              <ArrowRight size={16} />
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}
