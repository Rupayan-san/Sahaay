import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  Eye,
  FileImage,
  ImagePlus,
  Play,
  ShieldAlert,
  Star,
  XCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  assignVolunteer,
  completeAssignment,
  getIssueAssignments,
  rateAssignment,
  rejectAssignment,
  startAssignment,
  submitAssignment,
  verifyAssignment,
} from '../api/assignments';
import { getIssues } from '../api/issues';
import { verifyImages } from '../api/verification';
import { getVolunteers } from '../api/volunteers';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useAppStore } from '../store/useAppStore';
import type {
  Assignment,
  Issue,
  VerificationImageResult,
  VerificationLayerResult,
  VerificationResponse,
} from '../types';

interface AssignmentLocationState {
  issue?: Issue;
}

type AssignmentTab =
  | 'all'
  | 'applied'
  | 'assigned'
  | 'in_progress'
  | 'submitted'
  | 'verified'
  | 'completed'
  | 'rejected';

const assignmentTabs: { label: string; value: AssignmentTab }[] = [
  { label: 'All', value: 'all' },
  { label: 'Applied', value: 'applied' },
  { label: 'Assigned', value: 'assigned' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Submitted', value: 'submitted' },
  { label: 'Verified', value: 'verified' },
  { label: 'Completed', value: 'completed' },
  { label: 'Rejected', value: 'rejected' },
];

const API_BASE_URL = 'http://localhost:8000';

function formatDate(value?: string | null): string {
  if (!value) {
    return 'Not set';
  }
  return new Date(value).toLocaleString();
}

function buildImageUrl(path: string): string {
  const normalized = path.trim().replace(/\\/g, '/');
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized;
  }
  return `${API_BASE_URL}/${normalized.replace(/^\/+/, '')}`;
}

function statusTone(status: 'pass' | 'fail' | 'suspicious' | 'pass_fail'): string {
  if (status === 'fail') {
    return 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-300';
  }
  if (status === 'suspicious') {
    return 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-300';
  }
  return 'bg-teal/10 text-teal dark:bg-teal/20 dark:text-teal';
}

function renderLayerLabel(result: VerificationLayerResult): string {
  if (result.passed === true) {
    return 'Pass';
  }
  if (result.passed === false) {
    return 'Fail';
  }
  return 'Not checked';
}

function SubmissionImageGrid({
  title,
  imagePaths,
}: {
  title: string;
  imagePaths: string[];
}) {
  if (imagePaths.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="label-caps text-on-surface-variant dark:text-gray-500">{title}</p>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-on-surface dark:bg-gray-900 dark:text-gray-200">
          {imagePaths.length} image{imagePaths.length === 1 ? '' : 's'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {imagePaths.map((imagePath) => {
          const imageUrl = buildImageUrl(imagePath);
          return (
            <a
              key={imagePath}
              href={imageUrl}
              target="_blank"
              rel="noreferrer"
              className="group overflow-hidden rounded-[20px] border border-outline-variant bg-white dark:border-gray-800 dark:bg-gray-900"
              title={imagePath}
            >
              <img
                src={imageUrl}
                alt={`${title} evidence`}
                className="aspect-square w-full object-cover transition group-hover:scale-105"
                loading="lazy"
              />
              <div className="truncate px-3 py-2 text-xs font-medium text-on-surface-variant dark:text-gray-400">
                {imagePath.split('/').pop() ?? imagePath}
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}

function AssignmentSkeleton() {
  return (
    <div className="grid gap-4">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="card animate-pulse p-5">
          <div className="h-4 w-1/3 rounded-full bg-surface-container dark:bg-gray-800" />
          <div className="mt-4 h-6 w-2/3 rounded-full bg-surface-container dark:bg-gray-800" />
          <div className="mt-5 space-y-2">
            <div className="h-3 w-full rounded-full bg-surface-container dark:bg-gray-800" />
            <div className="h-3 w-3/4 rounded-full bg-surface-container dark:bg-gray-800" />
          </div>
        </div>
      ))}
    </div>
  );
}

function ModalShell({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string;
  subtitle: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-4 py-6 backdrop-blur-sm">
      <div className="card max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="label-caps text-on-surface-variant dark:text-gray-500">Assignment action</p>
            <h3 className="mt-2 text-2xl font-bold text-on-surface dark:text-white">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-on-surface-variant dark:text-gray-400">{subtitle}</p>
          </div>
          <button type="button" className="btn-outline" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="mt-6">{children}</div>
      </div>
    </div>
  );
}

function VerificationResultCard({ result }: { result: VerificationImageResult }) {
  const layers: { label: string; value: VerificationLayerResult }[] = [
    { label: 'Reverse search', value: result.checks.reverse_search },
    { label: 'AI generated', value: result.checks.ai_generated },
    { label: 'Duplicate check', value: result.checks.duplicate_check },
  ];

  return (
    <div className="rounded-[24px] border border-outline-variant bg-surface-container-low p-4 dark:border-gray-800 dark:bg-gray-950/70">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-on-surface dark:text-white">{result.image_path}</p>
          <p className="mt-1 text-xs text-on-surface-variant dark:text-gray-500">
            Final confidence {(result.final_confidence * 100).toFixed(0)}%
          </p>
        </div>
        <span
          className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusTone(result.overall_verdict)}`}
        >
          {result.overall_verdict}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {layers.map((layer) => (
          <div key={layer.label} className="rounded-2xl bg-white p-3 dark:bg-gray-900">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-on-surface-variant dark:text-gray-500">
                {layer.label}
              </p>
              <span
                className={`rounded-full px-2 py-1 text-[11px] font-semibold ${
                  layer.value.passed === false
                    ? statusTone('fail')
                    : layer.value.passed === true
                      ? statusTone('pass')
                      : 'bg-surface-container text-on-surface-variant dark:bg-gray-800 dark:text-gray-400'
                }`}
              >
                {renderLayerLabel(layer.value)}
              </span>
            </div>
            <p className="mt-3 text-lg font-bold text-on-surface dark:text-white">
              {(layer.value.confidence * 100).toFixed(0)}%
            </p>
            <p className="mt-2 text-xs leading-5 text-on-surface-variant dark:text-gray-400">
              {layer.value.notes || 'No additional notes provided.'}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AssignmentView() {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { actorId, actorRole, setActor } = useAppStore();
  const state = (location.state ?? {}) as AssignmentLocationState;
  const [activeTab, setActiveTab] = useState<AssignmentTab>('all');
  const [submitTarget, setSubmitTarget] = useState<Assignment | null>(null);
  const [submitForm, setSubmitForm] = useState({
    notes: '',
    before_images: [] as File[],
    after_images: [] as File[],
  });
  const [rejectTarget, setRejectTarget] = useState<Assignment | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [ratingTarget, setRatingTarget] = useState<Assignment | null>(null);
  const [ratingForm, setRatingForm] = useState({ stars: 5, review: '' });
  const [verificationPanels, setVerificationPanels] = useState<Record<string, VerificationResponse>>({});

  const issuesQuery = useQuery({
    queryKey: ['issues', 'assignment-view'],
    queryFn: async () => getIssues({ limit: 50, skip: 0 }),
  });

  const volunteersQuery = useQuery({
    queryKey: ['volunteers', 'assignment-view'],
    queryFn: async () => getVolunteers({ limit: 100, skip: 0 }),
  });

  const issueIds = useMemo(() => {
    if (state.issue?.issue_id) {
      return [state.issue.issue_id];
    }
    return (issuesQuery.data?.data ?? []).map((issue) => issue.issue_id);
  }, [issuesQuery.data?.data, state.issue?.issue_id]);

  const assignmentQueries = useQueries({
    queries: issueIds.map((issueId) => ({
      queryKey: ['issue-assignments', issueId, actorRole],
      queryFn: async () =>
        getIssueAssignments(issueId, {
          includeAllForVolunteerView: actorRole === 'volunteer',
        }),
      enabled: Boolean(issueId),
    })),
  });

  const assignMutation = useMutation({
    mutationFn: (assignmentId: string) => assignVolunteer(assignmentId),
    onSuccess: () => {
      toast.success('Volunteer assigned.');
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  const startMutation = useMutation({
    mutationFn: (assignmentId: string) => startAssignment(assignmentId),
    onSuccess: () => {
      toast.success('Assignment started.');
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
    },
  });

  const submitMutation = useMutation({
    mutationFn: ({ assignmentId, payload }: { assignmentId: string; payload: typeof submitForm }) =>
      submitAssignment(assignmentId, payload),
    onSuccess: () => {
      toast.success('Assignment submitted for verification.');
      setSubmitTarget(null);
      setSubmitForm({ notes: '', before_images: [], after_images: [] });
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  const completeMutation = useMutation({
    mutationFn: (assignment: Assignment) => completeAssignment(assignment.assignment_id),
    onSuccess: (_response, assignment) => {
      toast.success('Assignment completed.');
      setRatingTarget(assignment);
      setRatingForm({ stars: 5, review: '' });
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
    },
  });

  const verifyMutation = useMutation({
    mutationFn: async (assignment: Assignment) => {
      const imagePaths = assignment.submission_data?.after_images ?? [];
      if (imagePaths.length === 0) {
        throw new Error('No after images available for verification.');
      }

      const verification = await verifyImages(assignment.assignment_id, imagePaths);
      const hasVerificationRisk =
        verification.summary.failed > 0 || verification.summary.suspicious > 0;

      let updatedAssignment: Assignment | null = null;
      if (!hasVerificationRisk) {
        const response = await verifyAssignment(assignment.assignment_id);
        updatedAssignment = response.data;
      }

      return {
        assignmentId: assignment.assignment_id,
        verification,
        updatedAssignment,
      };
    },
    onSuccess: ({ assignmentId, verification, updatedAssignment }) => {
      setVerificationPanels((current) => ({
        ...current,
        [assignmentId]: verification,
      }));

      if (updatedAssignment) {
        toast.success('Assignment verified.');
        queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
        queryClient.invalidateQueries({ queryKey: ['issues'] });
        // If verification passed and the backend advanced the status to "verified",
        // streamline the flow by completing immediately.
        completeMutation.mutate(updatedAssignment);
      } else {
        toast.error('Verification flagged the submission for manual review.');
      }
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ assignmentId, reason }: { assignmentId: string; reason: string }) =>
      rejectAssignment(assignmentId, reason),
    onSuccess: () => {
      toast.success('Assignment rejected.');
      setRejectTarget(null);
      setRejectReason('');
      queryClient.invalidateQueries({ queryKey: ['issue-assignments'] });
      queryClient.invalidateQueries({ queryKey: ['issues'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  const ratingMutation = useMutation({
    mutationFn: ({
      assignmentId,
      stars,
      review,
    }: {
      assignmentId: string;
      stars: number;
      review?: string;
    }) => rateAssignment(assignmentId, stars, review),
    onSuccess: () => {
      toast.success('Rating submitted.');
      setRatingTarget(null);
      setRatingForm({ stars: 5, review: '' });
      queryClient.invalidateQueries({ queryKey: ['volunteers'] });
      queryClient.invalidateQueries({ queryKey: ['leaderboard'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
  });

  const issues = useMemo(() => issuesQuery.data?.data ?? [], [issuesQuery.data?.data]);
  const volunteers = useMemo(
    () => volunteersQuery.data?.data ?? [],
    [volunteersQuery.data?.data],
  );
  const issueMap = useMemo(() => {
    const items = state.issue ? [state.issue, ...issues] : issues;
    return new Map(items.map((issue) => [issue.issue_id, issue]));
  }, [issues, state.issue]);
  const volunteerMap = useMemo(
    () => new Map(volunteers.map((volunteer) => [volunteer.volunteer_id, volunteer])),
    [volunteers],
  );

  const allAssignments = useMemo(() => {
    const flattened = assignmentQueries.flatMap((query) => query.data?.data ?? []);
    const deduped = new Map(flattened.map((assignment) => [assignment.assignment_id, assignment]));
    return Array.from(deduped.values())
      .sort(
        (left, right) =>
          new Date(right.applied_at).getTime() - new Date(left.applied_at).getTime(),
      );
  }, [assignmentQueries]);

  const assignments = useMemo(
    () => allAssignments.filter((assignment) => (activeTab === 'all' ? true : assignment.status === activeTab)),
    [activeTab, allAssignments],
  );

  const loadingAssignments =
    issuesQuery.isPending ||
    volunteersQuery.isPending ||
    assignmentQueries.some((query) => query.isPending);

  useEffect(() => {
    if (actorRole !== 'volunteer' || loadingAssignments || allAssignments.length === 0) {
      return;
    }

    const actionable = allAssignments.find(
      (assignment) => assignment.status === 'in_progress' || assignment.status === 'assigned',
    );

    const actorHasActionable = allAssignments.some(
      (assignment) =>
        assignment.volunteer_id === actorId &&
        (assignment.status === 'in_progress' || assignment.status === 'assigned'),
    );

    // If the currently active volunteer doesn't have any actionable assignments, but someone does,
    // switch to the volunteer that can actually take action.
    if (!actorHasActionable && actionable) {
      setActor('volunteer', actionable.volunteer_id);
      return;
    }

    const actorHasAssignments = allAssignments.some((assignment) => assignment.volunteer_id === actorId);
    if (!actorHasAssignments) {
      // Fall back to the most recent assignment's volunteer id.
      setActor('volunteer', allAssignments[0].volunteer_id);
      return;
    }

    // Default volunteers into an actionable tab.
    if (activeTab === 'all') {
      const hasAssigned = allAssignments.some(
        (assignment) => assignment.volunteer_id === actorId && assignment.status === 'assigned',
      );
      const hasInProgress = allAssignments.some(
        (assignment) => assignment.volunteer_id === actorId && assignment.status === 'in_progress',
      );
      if (hasInProgress) {
        setActiveTab('in_progress');
      } else if (hasAssigned) {
        setActiveTab('assigned');
      }
    }
  }, [actorId, actorRole, activeTab, allAssignments, loadingAssignments, setActor]);

  const handleSubmitAction = () => {
    if (!submitTarget) {
      return;
    }
    if (submitForm.after_images.length === 0) {
      toast.error('Please upload at least one after image.');
      return;
    }

    submitMutation.mutate({
      assignmentId: submitTarget.assignment_id,
      payload: submitForm,
    });
  };

  const handleRejectAction = () => {
    if (!rejectTarget) {
      return;
    }
    if (!rejectReason.trim()) {
      toast.error('Please include a rejection reason.');
      return;
    }

    rejectMutation.mutate({
      assignmentId: rejectTarget.assignment_id,
      reason: rejectReason.trim(),
    });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <section className="rounded-[32px] bg-gradient-to-r from-slate-900 to-primary px-6 py-8 text-white shadow-xl sm:px-8">
        <p className="label-caps text-white/70">Assignment workflow</p>
        <h2 className="mt-3 font-heading text-3xl font-bold tracking-tight sm:text-4xl">
          Track applications, field work, and verification in one place.
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-white/80 sm:text-base">
          {actorRole === 'admin'
            ? 'Review volunteer applications, verify submitted evidence, and close the loop with ratings.'
            : 'Stay on top of your applications, active work, and submission requirements.'}
        </p>
      </section>

      {state.issue ? (
        <div className="card flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="label-caps text-on-surface-variant dark:text-gray-500">Filtered issue</p>
            <h3 className="mt-2 text-xl font-bold text-on-surface dark:text-white">{state.issue.title}</h3>
            <p className="mt-1 text-sm text-on-surface-variant dark:text-gray-400">{state.issue.location}</p>
          </div>
          <button type="button" className="btn-outline" onClick={() => navigate('/issues')}>
            Back to issue board
          </button>
        </div>
      ) : null}

      <div className="rounded-[28px] border border-outline-variant bg-surface-container-low p-2 dark:border-gray-800 dark:bg-gray-900/70">
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-8">
          {assignmentTabs.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setActiveTab(tab.value)}
              className={`rounded-[22px] px-4 py-3 text-sm font-semibold transition ${
                activeTab === tab.value
                  ? 'bg-white text-primary shadow-sm dark:bg-gray-950 dark:text-white'
                  : 'text-on-surface-variant hover:bg-white/60 dark:text-gray-400 dark:hover:bg-gray-950/50'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {loadingAssignments ? <AssignmentSkeleton /> : null}

      {!loadingAssignments && assignments.length === 0 ? (
        <EmptyState
          title={actorRole === 'admin' ? 'No assignments found' : 'No assignments for you yet'}
          message={
            actorRole === 'admin'
              ? 'Assignments will appear here as volunteers apply to issues.'
              : 'Once you are assigned to work, your task history will show up here. If you do not see Start/Submit, check the active actor id in the top bar.'
          }
        />
      ) : null}

      {!loadingAssignments ? (
        <div className="grid gap-4">
          {assignments.map((assignment) => {
            const issue = issueMap.get(assignment.issue_id);
            const volunteer = volunteerMap.get(assignment.volunteer_id);
            const verification = verificationPanels[assignment.assignment_id];

            return (
              <article key={assignment.assignment_id} className="card p-5 sm:p-6">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={assignment.status} />
                      {issue ? (
                        <button
                          type="button"
                          className="rounded-full bg-surface-container px-3 py-1 text-xs font-semibold text-on-surface-variant transition hover:text-primary dark:bg-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                          onClick={() => navigate('/issues')}
                        >
                          {issue.title}
                        </button>
                      ) : null}
                    </div>

                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="label-caps text-on-surface-variant dark:text-gray-500">Issue title</p>
                        <h3 className="mt-2 text-xl font-bold text-on-surface dark:text-white">
                          {issue?.title ?? assignment.issue_id}
                        </h3>
                        <p className="mt-2 text-sm text-on-surface-variant dark:text-gray-400">
                          {issue?.location ?? 'Location unavailable'}
                        </p>
                      </div>
                      <div>
                        <p className="label-caps text-on-surface-variant dark:text-gray-500">Volunteer</p>
                        <p className="mt-2 text-lg font-semibold text-on-surface dark:text-white">
                          {volunteer?.name ?? assignment.volunteer_id}
                        </p>
                        <p className="mt-2 text-sm text-on-surface-variant dark:text-gray-400">
                          {volunteer?.email ?? 'No volunteer email available'}
                        </p>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                      <div className="rounded-[20px] bg-surface-container-low p-4 dark:bg-gray-950/60">
                        <p className="text-xs text-on-surface-variant dark:text-gray-500">Applied</p>
                        <p className="mt-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                          {formatDate(assignment.applied_at)}
                        </p>
                      </div>
                      <div className="rounded-[20px] bg-surface-container-low p-4 dark:bg-gray-950/60">
                        <p className="text-xs text-on-surface-variant dark:text-gray-500">Assigned</p>
                        <p className="mt-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                          {formatDate(assignment.assigned_at)}
                        </p>
                      </div>
                      <div className="rounded-[20px] bg-surface-container-low p-4 dark:bg-gray-950/60">
                        <p className="text-xs text-on-surface-variant dark:text-gray-500">Submitted</p>
                        <p className="mt-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                          {formatDate(assignment.submitted_at)}
                        </p>
                      </div>
                      <div className="rounded-[20px] bg-surface-container-low p-4 dark:bg-gray-950/60">
                        <p className="text-xs text-on-surface-variant dark:text-gray-500">Completed</p>
                        <p className="mt-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                          {formatDate(assignment.completed_at)}
                        </p>
                      </div>
                    </div>

                    {assignment.submission_data ? (
                      <div className="mt-5 rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70">
                        <div className="flex items-center gap-2 text-sm font-semibold text-on-surface dark:text-gray-100">
                          <FileImage size={16} />
                          Submission data
                        </div>
                        <p className="mt-3 text-sm leading-6 text-on-surface-variant dark:text-gray-400">
                          {assignment.submission_data.notes || 'No notes were added to this submission.'}
                        </p>
                        <div className="mt-3 flex flex-wrap gap-2 text-xs">
                          <span className="rounded-full bg-white px-3 py-1 font-semibold text-on-surface dark:bg-gray-900 dark:text-gray-200">
                            {assignment.submission_data.before_images.length} before images
                          </span>
                          <span className="rounded-full bg-white px-3 py-1 font-semibold text-on-surface dark:bg-gray-900 dark:text-gray-200">
                            {assignment.submission_data.after_images.length} after images
                          </span>
                        </div>
                        <div className="mt-5 space-y-5">
                          <SubmissionImageGrid
                            title="Before images"
                            imagePaths={assignment.submission_data.before_images}
                          />
                          <SubmissionImageGrid
                            title="After images"
                            imagePaths={assignment.submission_data.after_images}
                          />
                        </div>
                      </div>
                    ) : null}

                    {assignment.admin_notes ? (
                      <div className="mt-5 rounded-[24px] bg-red-50 p-4 dark:bg-red-950/20">
                        <p className="text-sm font-semibold text-red-600 dark:text-red-300">Admin notes</p>
                        <p className="mt-2 text-sm leading-6 text-red-700 dark:text-red-200">
                          {assignment.admin_notes}
                        </p>
                      </div>
                    ) : null}

                    {verification ? (
                      <div className="mt-5 space-y-4">
                        <div className="rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70">
                          <p className="label-caps text-on-surface-variant dark:text-gray-500">
                            Verification summary
                          </p>
                          <div className="mt-3 flex flex-wrap gap-2 text-sm">
                            <span className="rounded-full bg-white px-3 py-1 font-semibold text-teal dark:bg-gray-900">
                              {verification.summary.passed} passed
                            </span>
                            <span className="rounded-full bg-white px-3 py-1 font-semibold text-red-600 dark:bg-gray-900 dark:text-red-300">
                              {verification.summary.failed} failed
                            </span>
                            <span className="rounded-full bg-white px-3 py-1 font-semibold text-amber-600 dark:bg-gray-900 dark:text-amber-300">
                              {verification.summary.suspicious} suspicious
                            </span>
                          </div>
                        </div>
                        {verification.results.map((result) => (
                          <VerificationResultCard key={result.image_path} result={result} />
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <aside className="w-full shrink-0 rounded-[24px] bg-surface-container p-4 dark:bg-gray-950/70 lg:w-64">
                    <p className="label-caps text-on-surface-variant dark:text-gray-500">Actions</p>
                    <div className="mt-4 space-y-3">
                      {actorRole === 'volunteer' ? (
                        <div className="rounded-[20px] bg-white p-3 text-xs text-on-surface-variant dark:bg-gray-900 dark:text-gray-400">
                          <p>
                            Active actor: <span className="font-semibold">{actorId.slice(0, 8)}</span>
                          </p>
                          <p>
                            Assigned to: <span className="font-semibold">{assignment.volunteer_id.slice(0, 8)}</span>
                          </p>
                          <p>
                            Status: <span className="font-semibold capitalize">{assignment.status}</span>
                          </p>
                        </div>
                      ) : null}

                      {actorRole === 'volunteer' && assignment.volunteer_id !== actorId ? (
                        <button
                          type="button"
                          className="btn-outline inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => setActor('volunteer', assignment.volunteer_id)}
                        >
                          Switch to this volunteer
                        </button>
                      ) : null}

                      {actorRole === 'admin' && assignment.status === 'applied' ? (
                        <button
                          type="button"
                          className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => assignMutation.mutate(assignment.assignment_id)}
                          disabled={assignMutation.isPending}
                        >
                          <CheckCircle2 size={16} />
                          Assign
                        </button>
                      ) : null}

                      {actorRole === 'volunteer' &&
                      assignment.volunteer_id === actorId &&
                      assignment.status === 'assigned' ? (
                        <button
                          type="button"
                          className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => startMutation.mutate(assignment.assignment_id)}
                          disabled={startMutation.isPending}
                        >
                          <Play size={16} />
                          Start
                        </button>
                      ) : null}

                      {actorRole === 'volunteer' &&
                      assignment.volunteer_id === actorId &&
                      assignment.status === 'in_progress' ? (
                        <button
                          type="button"
                          className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => setSubmitTarget(assignment)}
                        >
                          <ImagePlus size={16} />
                          Submit
                        </button>
                      ) : null}

                      {actorRole === 'volunteer' &&
                      assignment.volunteer_id === actorId &&
                      assignment.status !== 'assigned' &&
                      assignment.status !== 'in_progress' ? (
                        <div className="rounded-[20px] bg-surface-container-low p-3 text-sm text-on-surface-variant dark:bg-gray-950/60 dark:text-gray-400">
                          {assignment.status === 'applied'
                            ? 'Waiting for an admin to assign you.'
                            : assignment.status === 'submitted'
                              ? 'Submitted — waiting for admin verification.'
                              : assignment.status === 'verified'
                                ? 'Verified — waiting for admin completion.'
                                : assignment.status === 'completed'
                                  ? 'Completed.'
                                  : assignment.status === 'rejected'
                                    ? 'Rejected — check admin notes.'
                                    : 'No actions available for this status.'}
                        </div>
                      ) : null}

                      {actorRole === 'admin' && assignment.status === 'submitted' ? (
                        <button
                          type="button"
                          className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => verifyMutation.mutate(assignment)}
                          disabled={verifyMutation.isPending || completeMutation.isPending}
                        >
                          <Eye size={16} />
                          {verifyMutation.isPending || completeMutation.isPending ? 'Verifying...' : 'Verify & complete'}
                        </button>
                      ) : null}

                      {actorRole === 'admin' && assignment.status === 'verified' ? (
                        <button
                          type="button"
                          className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => completeMutation.mutate(assignment)}
                          disabled={completeMutation.isPending}
                        >
                          <CheckCircle2 size={16} />
                          Complete
                        </button>
                      ) : null}

                      {actorRole === 'admin' && assignment.status === 'completed' ? (
                        <button
                          type="button"
                          className="btn-outline inline-flex w-full items-center justify-center gap-2 py-3"
                          onClick={() => {
                            setRatingTarget(assignment);
                            setRatingForm({ stars: 5, review: '' });
                          }}
                        >
                          <Star size={16} />
                          Rate
                        </button>
                      ) : null}

                      {actorRole === 'admin' && assignment.status !== 'rejected' ? (
                        <button
                          type="button"
                          className="btn-outline inline-flex w-full items-center justify-center gap-2 border-red-300 text-red-600 hover:bg-red-50 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/20"
                          onClick={() => setRejectTarget(assignment)}
                        >
                          <XCircle size={16} />
                          Reject
                        </button>
                      ) : null}
                    </div>
                  </aside>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}

      {submitTarget ? (
        <ModalShell
          title="Submit assignment"
          subtitle="Upload before and after evidence so the admin can review and verify the work."
          onClose={() => {
            setSubmitTarget(null);
            setSubmitForm({ notes: '', before_images: [], after_images: [] });
          }}
        >
          <div className="space-y-4">
            <textarea
              value={submitForm.notes}
              onChange={(event) =>
                setSubmitForm((current) => ({ ...current, notes: event.target.value }))
              }
              className="input-field min-h-[140px] resize-none"
              placeholder="Summarize what was done, blockers you faced, and any follow-up needed."
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2">
                <span className="label-caps text-on-surface-variant dark:text-gray-500">Before images</span>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  className="input-field file:mr-4 file:rounded-full file:border-0 file:bg-surface-container file:px-3 file:py-2 file:text-sm file:font-semibold"
                  onChange={(event) =>
                    setSubmitForm((current) => ({
                      ...current,
                      before_images: Array.from(event.target.files ?? []),
                    }))
                  }
                />
              </label>
              <label className="space-y-2">
                <span className="label-caps text-on-surface-variant dark:text-gray-500">After images</span>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  className="input-field file:mr-4 file:rounded-full file:border-0 file:bg-surface-container file:px-3 file:py-2 file:text-sm file:font-semibold"
                  onChange={(event) =>
                    setSubmitForm((current) => ({
                      ...current,
                      after_images: Array.from(event.target.files ?? []),
                    }))
                  }
                />
              </label>
            </div>
            <div className="grid gap-3 text-sm text-on-surface-variant dark:text-gray-400 sm:grid-cols-2">
              <div className="rounded-[20px] bg-surface-container p-4 dark:bg-gray-950/70">
                {submitForm.before_images.length} before image(s) selected
              </div>
              <div className="rounded-[20px] bg-surface-container p-4 dark:bg-gray-950/70">
                {submitForm.after_images.length} after image(s) selected
              </div>
            </div>
            <button
              type="button"
              className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
              onClick={handleSubmitAction}
              disabled={submitMutation.isPending}
            >
              <ImagePlus size={16} />
              {submitMutation.isPending ? 'Submitting...' : 'Submit assignment'}
            </button>
          </div>
        </ModalShell>
      ) : null}

      {rejectTarget ? (
        <ModalShell
          title="Reject assignment"
          subtitle="Add a clear reason so the volunteer understands what needs to be corrected."
          onClose={() => {
            setRejectTarget(null);
            setRejectReason('');
          }}
        >
          <div className="space-y-4">
            <textarea
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
              className="input-field min-h-[140px] resize-none"
              placeholder="Explain why the assignment is being rejected."
            />
            <button
              type="button"
              className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
              onClick={handleRejectAction}
              disabled={rejectMutation.isPending}
            >
              <ShieldAlert size={16} />
              {rejectMutation.isPending ? 'Rejecting...' : 'Reject assignment'}
            </button>
          </div>
        </ModalShell>
      ) : null}

      {ratingTarget ? (
        <ModalShell
          title="Rate completed assignment"
          subtitle="Capture quick feedback so trust scores and leaderboard standings stay up to date."
          onClose={() => {
            setRatingTarget(null);
            setRatingForm({ stars: 5, review: '' });
          }}
        >
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              {Array.from({ length: 5 }).map((_, index) => {
                const stars = index + 1;
                const active = stars <= ratingForm.stars;

                return (
                  <button
                    key={stars}
                    type="button"
                    className={`flex h-12 w-12 items-center justify-center rounded-2xl border transition ${
                      active
                        ? 'border-amber-300 bg-amber-50 text-amber-500 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-300'
                        : 'border-outline-variant text-on-surface-variant dark:border-gray-800 dark:text-gray-500'
                    }`}
                    onClick={() => setRatingForm((current) => ({ ...current, stars }))}
                  >
                    <Star size={18} fill={active ? 'currentColor' : 'none'} />
                  </button>
                );
              })}
            </div>

            <textarea
              value={ratingForm.review}
              onChange={(event) =>
                setRatingForm((current) => ({ ...current, review: event.target.value }))
              }
              className="input-field min-h-[140px] resize-none"
              placeholder="Optional review for the volunteer."
            />
            <button
              type="button"
              className="btn-primary inline-flex w-full items-center justify-center gap-2 py-3"
              onClick={() => {
                if (!ratingTarget) {
                  return;
                }

                ratingMutation.mutate({
                  assignmentId: ratingTarget.assignment_id,
                  stars: ratingForm.stars,
                  review: ratingForm.review.trim() || undefined,
                });
              }}
              disabled={ratingMutation.isPending}
            >
              <Star size={16} />
              {ratingMutation.isPending ? 'Saving rating...' : 'Submit rating'}
            </button>
          </div>
        </ModalShell>
      ) : null}
    </div>
  );
}
