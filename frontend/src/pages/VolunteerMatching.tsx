import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ChevronDown,
  ChevronUp,
  MapPin,
  Sparkles,
  UserPlus,
  Wrench,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useLocation } from 'react-router-dom';
import { applyToIssueAsVolunteer, assignVolunteer } from '../api/assignments';
import { getIssues } from '../api/issues';
import { getVolunteers, matchVolunteers, registerVolunteer } from '../api/volunteers';
import { EmptyState } from '../components/ui/EmptyState';
import { LoadingSpinner } from '../components/ui/LoadingSpinner';
import { TrustScoreBar } from '../components/ui/TrustScoreBar';
import { useAppStore } from '../store/useAppStore';
import type { Issue, Volunteer, VolunteerMatch } from '../types';

interface MatchingLocationState {
  issue?: Issue;
}

function BreakdownBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold uppercase tracking-[0.18em] text-on-surface-variant dark:text-gray-500">
          {label}
        </span>
        <span className="font-semibold text-on-surface dark:text-gray-200">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-surface-container dark:bg-gray-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-secondary to-primary"
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
        />
      </div>
    </div>
  );
}

function MatchCard({
  issueId,
  match,
  volunteer,
  isAdmin,
  onAssign,
  assigningVolunteerId,
}: {
  issueId: string;
  match: VolunteerMatch;
  volunteer?: Volunteer;
  isAdmin: boolean;
  onAssign: (issueId: string, volunteerId: string) => void;
  assigningVolunteerId?: string;
}) {
  const locationLabel = volunteer
    ? [volunteer.location.city, volunteer.location.district, volunteer.location.state]
        .filter(Boolean)
        .join(', ')
    : 'Location unavailable';

  return (
    <article className="card p-5 sm:p-6">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h3 className="text-2xl font-heading font-bold text-on-surface dark:text-white">{match.name}</h3>
              <div className="mt-2 flex items-center gap-2 text-sm text-on-surface-variant dark:text-gray-400">
                <MapPin size={14} />
                <span className="truncate">{locationLabel}</span>
              </div>
            </div>
            <div className="rounded-[24px] bg-primary px-4 py-3 text-center text-white shadow-sm">
              <p className="text-3xl font-heading font-bold">{(match.match_score * 100).toFixed(0)}%</p>
              <p className="label-caps text-white/70">Match score</p>
            </div>
          </div>

          <div className="mt-5 rounded-[24px] bg-surface-container-low p-4 dark:bg-gray-950/60">
            <div className="flex items-center gap-2 text-sm font-semibold text-on-surface dark:text-gray-100">
              <Wrench size={16} />
              Skills
            </div>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">{match.skills}</p>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <BreakdownBar label="Skill similarity" value={match.breakdown.skill_similarity} />
            <BreakdownBar label="Location match" value={match.breakdown.location_match} />
            <BreakdownBar label="Performance boost" value={match.breakdown.performance_boost} />
          </div>
        </div>

        <aside className="w-full shrink-0 rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70 lg:w-64">
          <p className="label-caps text-on-surface-variant dark:text-gray-500">Volunteer profile</p>
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-xs text-on-surface-variant dark:text-gray-500">Trust score</p>
              <div className="mt-2">
                <TrustScoreBar score={match.trust_score} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-2xl bg-white p-3 dark:bg-gray-900">
                <p className="text-xs text-on-surface-variant dark:text-gray-500">Completed</p>
                <p className="mt-1 font-semibold text-on-surface dark:text-gray-100">{match.tasks_completed}</p>
              </div>
              <div className="rounded-2xl bg-white p-3 dark:bg-gray-900">
                <p className="text-xs text-on-surface-variant dark:text-gray-500">Badges</p>
                <p className="mt-1 font-semibold text-on-surface dark:text-gray-100">
                  {volunteer?.badges?.length ?? 0}
                </p>
              </div>
            </div>

            {isAdmin ? (
              <button
                type="button"
                className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                onClick={() => onAssign(issueId, match.volunteer_id)}
                disabled={assigningVolunteerId === match.volunteer_id}
              >
                <Sparkles size={16} />
                {assigningVolunteerId === match.volunteer_id ? 'Assigning...' : 'Assign'}
              </button>
            ) : null}
          </div>
        </aside>
      </div>
    </article>
  );
}

export function VolunteerMatching() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const { actorRole } = useAppStore();
  const state = (location.state ?? {}) as MatchingLocationState;
  const routeIssue = state.issue;
  const [selectedIssueId, setSelectedIssueId] = useState(routeIssue?.issue_id ?? '');
  const [showRegistration, setShowRegistration] = useState(false);
  const [registration, setRegistration] = useState({
    name: '',
    email: '',
    skills: '',
    city: '',
    district: '',
    state: '',
  });

  const issuesQuery = useQuery({
    queryKey: ['issues', 'matching', 'open'],
    queryFn: async () => getIssues({ limit: 50, skip: 0, status: 'open' }),
  });

  const volunteersQuery = useQuery({
    queryKey: ['volunteers', 'active'],
    queryFn: async () => getVolunteers({ limit: 100, skip: 0, active_only: true }),
  });

  const matchesQuery = useQuery({
    queryKey: ['volunteer-matches', selectedIssueId],
    queryFn: async () => matchVolunteers(selectedIssueId),
    enabled: Boolean(selectedIssueId),
  });

  const registerMutation = useMutation({
    mutationFn: registerVolunteer,
    onSuccess: () => {
      toast.success('Volunteer registered!');
      setRegistration({
        name: '',
        email: '',
        skills: '',
        city: '',
        district: '',
        state: '',
      });
      setShowRegistration(false);
      queryClient.invalidateQueries({ queryKey: ['volunteers'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    },
  });

  const assignMutation = useMutation({
    mutationFn: async ({ issueId, volunteerId }: { issueId: string; volunteerId: string }) => {
      const application = await applyToIssueAsVolunteer(
        issueId,
        volunteerId,
        'Auto-created from the matching console.',
      );
      return assignVolunteer(application.data.assignment_id);
    },
    onSuccess: () => {
      toast.success('Volunteer assigned successfully.');
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  const issues = useMemo(() => issuesQuery.data?.data ?? [], [issuesQuery.data?.data]);
  const volunteers = useMemo(
    () => volunteersQuery.data?.data ?? [],
    [volunteersQuery.data?.data],
  );
  const volunteerMap = useMemo(
    () => new Map(volunteers.map((volunteer) => [volunteer.volunteer_id, volunteer])),
    [volunteers],
  );
  const selectedIssue = useMemo(() => {
    if (!selectedIssueId) {
      return routeIssue;
    }
    return issues.find((issue) => issue.issue_id === selectedIssueId) ?? routeIssue;
  }, [issues, routeIssue, selectedIssueId]);
  const matches = matchesQuery.data?.matches ?? [];

  const handleRegister = () => {
    if (
      !registration.name.trim() ||
      !registration.email.trim() ||
      !registration.skills.trim() ||
      !registration.city.trim() ||
      !registration.district.trim() ||
      !registration.state.trim()
    ) {
      toast.error('Please complete all volunteer fields.');
      return;
    }

    registerMutation.mutate({
      name: registration.name.trim(),
      email: registration.email.trim(),
      skills: registration.skills.trim(),
      location: {
        city: registration.city.trim(),
        district: registration.district.trim(),
        state: registration.state.trim(),
      },
    });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="rounded-[32px] bg-gradient-to-r from-secondary to-slate-900 px-6 py-8 text-white shadow-xl sm:px-8">
        <p className="label-caps text-white/70">Matching engine</p>
        <h2 className="mt-3 font-heading text-3xl font-bold tracking-tight sm:text-4xl">
          Rank the best volunteers for each live issue.
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-white/80 sm:text-base">
          Skill similarity, geography, and trust are blended into one score so assignments can happen quickly and transparently.
        </p>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <section className="card p-6">
          <div className="grid gap-4 lg:grid-cols-[1fr_auto]">
            <label className="space-y-2 text-sm">
              <span className="label-caps text-on-surface-variant dark:text-gray-500">Issue</span>
              <select
                value={selectedIssueId}
                onChange={(event) => setSelectedIssueId(event.target.value)}
                className="input-field"
              >
                <option value="">Select an issue to match</option>
                {issues.map((issue) => (
                  <option key={issue.issue_id} value={issue.issue_id}>
                    {issue.title} - {issue.location}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              className="btn-outline inline-flex items-center justify-center gap-2"
              onClick={() => {
                if (!selectedIssueId) {
                  toast.error('Choose an issue first.');
                  return;
                }
                matchesQuery.refetch();
              }}
              disabled={!selectedIssueId || matchesQuery.isFetching}
            >
              <Sparkles size={16} />
              Refresh matches
            </button>
          </div>

          {selectedIssue ? (
            <div className="mt-5 rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-on-surface dark:bg-gray-900 dark:text-gray-200">
                  {selectedIssue.location}
                </span>
                <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary/20 dark:text-primary-200">
                  {selectedIssue.priority_score} priority
                </span>
              </div>
              <h3 className="mt-3 text-xl font-bold text-on-surface dark:text-white">{selectedIssue.title}</h3>
              <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                {selectedIssue.description}
              </p>
            </div>
          ) : null}

          <div className="mt-6">
            {issuesQuery.isPending || volunteersQuery.isPending ? (
              <LoadingSpinner message="Loading issues and volunteers..." />
            ) : null}

            {!issuesQuery.isPending && !selectedIssueId ? (
              <EmptyState
                title="Choose an issue to start matching"
                message="Select an open issue and the engine will surface the top volunteers."
              />
            ) : null}

            {selectedIssueId && matchesQuery.isPending ? (
              <LoadingSpinner message="Calculating the top volunteer matches..." />
            ) : null}

            {selectedIssueId && !matchesQuery.isPending && matches.length === 0 ? (
              <EmptyState
                title="No strong matches found"
                message="No active volunteers cleared the scoring threshold for this issue."
              />
            ) : null}

            {matches.length > 0 ? (
              <div className="space-y-4">
                {matches.map((match) => (
                  <MatchCard
                    key={match.volunteer_id}
                    issueId={selectedIssueId}
                    match={match}
                    volunteer={volunteerMap.get(match.volunteer_id)}
                    isAdmin={actorRole === 'admin'}
                    onAssign={(issueId, volunteerId) =>
                      assignMutation.mutate({ issueId, volunteerId })
                    }
                    assigningVolunteerId={assignMutation.isPending ? assignMutation.variables?.volunteerId : undefined}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </section>

        <aside className="space-y-4">
          <button
            type="button"
            className="card flex w-full items-center justify-between p-5 text-left"
            onClick={() => setShowRegistration((value) => !value)}
          >
            <div>
              <p className="label-caps text-on-surface-variant dark:text-gray-500">Volunteer onboarding</p>
              <h3 className="mt-2 text-xl font-bold text-on-surface dark:text-white">Register a volunteer</h3>
            </div>
            {showRegistration ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>

          {showRegistration ? (
            <div className="card space-y-4 p-5">
              <div className="rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70">
                <div className="flex items-center gap-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                  <UserPlus size={16} />
                  Quick registration
                </div>
                <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                  Add a new volunteer profile, generate their skills embedding, and make them available for matching immediately.
                </p>
              </div>

              <input
                value={registration.name}
                onChange={(event) =>
                  setRegistration((current) => ({ ...current, name: event.target.value }))
                }
                className="input-field"
                placeholder="Full name"
              />
              <input
                value={registration.email}
                onChange={(event) =>
                  setRegistration((current) => ({ ...current, email: event.target.value }))
                }
                className="input-field"
                placeholder="Email address"
                type="email"
              />
              <textarea
                value={registration.skills}
                onChange={(event) =>
                  setRegistration((current) => ({ ...current, skills: event.target.value }))
                }
                className="input-field min-h-[130px] resize-none"
                placeholder="Describe skills, tools, field experience, and categories of work."
              />
              <div className="grid gap-3 sm:grid-cols-3">
                <input
                  value={registration.city}
                  onChange={(event) =>
                    setRegistration((current) => ({ ...current, city: event.target.value }))
                  }
                  className="input-field"
                  placeholder="City"
                />
                <input
                  value={registration.district}
                  onChange={(event) =>
                    setRegistration((current) => ({ ...current, district: event.target.value }))
                  }
                  className="input-field"
                  placeholder="District"
                />
                <input
                  value={registration.state}
                  onChange={(event) =>
                    setRegistration((current) => ({ ...current, state: event.target.value }))
                  }
                  className="input-field"
                  placeholder="State"
                />
              </div>
              <button
                type="button"
                className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                onClick={handleRegister}
                disabled={registerMutation.isPending}
              >
                <UserPlus size={16} />
                {registerMutation.isPending ? 'Registering...' : 'Register volunteer'}
              </button>
            </div>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
