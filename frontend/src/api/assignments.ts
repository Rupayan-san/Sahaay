import axios from 'axios';
import apiClient from './client';
import type { Assignment, RatingResponse } from '../types';

const ASSIGNMENT_CACHE_KEY = 'sahaay_assignments_cache';
const DEFAULT_ADMIN_ID = '3b0d4d88-2f30-4e97-81d3-2bb8d0a55a11';

function readActorId(): string {
  return localStorage.getItem('actorId') ?? '';
}

function getCachedAssignments(): Assignment[] {
  try {
    const storedAssignments = localStorage.getItem(ASSIGNMENT_CACHE_KEY);
    if (!storedAssignments) {
      return [];
    }

    const parsed = JSON.parse(storedAssignments);
    return Array.isArray(parsed) ? (parsed as Assignment[]) : [];
  } catch {
    return [];
  }
}

function writeCachedAssignments(assignments: Assignment[]): void {
  localStorage.setItem(ASSIGNMENT_CACHE_KEY, JSON.stringify(assignments));
}

function cacheAssignment(assignment: Assignment): void {
  const assignments = getCachedAssignments();
  const nextAssignments = assignments.some((item) => item.assignment_id === assignment.assignment_id)
    ? assignments.map((item) => (item.assignment_id === assignment.assignment_id ? assignment : item))
    : [assignment, ...assignments];
  writeCachedAssignments(nextAssignments);
}

async function postActorScopedAssignment(
  path: string,
  payload: Record<string, unknown>,
): Promise<{ data: Assignment }> {
  const response = await apiClient.post<{ data: Assignment }>(path, payload);
  cacheAssignment(response.data.data);
  return response.data;
}

export async function applyToIssue(issueId: string, message?: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/issues/${issueId}/apply`, {
    volunteer_id: readActorId(),
    ...(message ? { message } : {}),
  });
}

export async function applyToIssueAsVolunteer(
  issueId: string,
  volunteerId: string,
  message?: string,
): Promise<{ data: Assignment }> {
  const response = await apiClient.post<{ data: Assignment }>(
    `/api/issues/${issueId}/apply`,
    {
      volunteer_id: volunteerId,
      ...(message ? { message } : {}),
    },
    {
      headers: {
        'X-Actor-Id': volunteerId,
        'X-Actor-Role': 'volunteer',
      },
    },
  );
  cacheAssignment(response.data.data);
  return response.data;
}

export async function assignVolunteer(assignmentId: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/assignments/${assignmentId}/assign`, {
    admin_id: readActorId(),
  });
}

export async function startAssignment(assignmentId: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/assignments/${assignmentId}/start`, {});
}

export async function submitAssignment(
  assignmentId: string,
  payload: {
    notes: string;
    before_images: File[];
    after_images: File[];
  },
): Promise<{ data: Assignment }> {
  const formData = new FormData();
  formData.append('notes', payload.notes);
  payload.before_images.forEach((file) => formData.append('before_images', file));
  payload.after_images.forEach((file) => formData.append('after_images', file));

  const response = await apiClient.post<{ data: Assignment }>(
    `/api/assignments/${assignmentId}/submit`,
    formData,
  );
  cacheAssignment(response.data.data);
  return response.data;
}

export async function verifyAssignment(assignmentId: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/assignments/${assignmentId}/verify`, {
    admin_id: readActorId(),
  });
}

export async function completeAssignment(assignmentId: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/assignments/${assignmentId}/complete`, {
    admin_id: readActorId(),
  });
}

export async function rejectAssignment(assignmentId: string, reason: string): Promise<{ data: Assignment }> {
  return postActorScopedAssignment(`/api/assignments/${assignmentId}/reject`, {
    admin_id: readActorId(),
    admin_notes: reason,
  });
}

export async function getIssueAssignments(
  issueId: string,
  options?: { includeAllForVolunteerView?: boolean },
): Promise<{ data: Assignment[] }> {
  try {
    const response = await apiClient.get<{ data: Assignment[] }>(
      `/api/issues/${issueId}/assignments`,
      options?.includeAllForVolunteerView
        ? {
            headers: {
              'X-Actor-Id': DEFAULT_ADMIN_ID,
              'X-Actor-Role': 'admin',
            },
          }
        : undefined,
    );
    response.data.data.forEach(cacheAssignment);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      const cachedAssignments = getCachedAssignments().filter((assignment) => assignment.issue_id === issueId);
      return { data: cachedAssignments };
    }
    throw error;
  }
}

export async function rateAssignment(
  assignmentId: string,
  stars: number,
  review?: string,
): Promise<void> {
  await apiClient.post<RatingResponse>(`/api/assignments/${assignmentId}/rate`, {
    stars,
    ...(review ? { review } : {}),
  });
}
