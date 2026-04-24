import apiClient from './client';
import type { Volunteer, VolunteerMatch, VolunteerLocation } from '../types';

export async function registerVolunteer(payload: {
  name: string;
  email: string;
  skills: string;
  location: VolunteerLocation;
}): Promise<{ data: Volunteer }> {
  const response = await apiClient.post<{ data: Volunteer }>('/api/volunteers', payload);
  return response.data;
}

export async function getVolunteers(params?: {
  limit?: number;
  skip?: number;
  active_only?: boolean;
}): Promise<{ data: Volunteer[] }> {
  const response = await apiClient.get<{ data: Volunteer[] }>('/api/volunteers', {
    params,
  });
  return response.data;
}

export async function matchVolunteers(issueId: string): Promise<{ matches: VolunteerMatch[] }> {
  const response = await apiClient.post<{ matches: VolunteerMatch[] }>(`/api/issues/${issueId}/match`);
  return response.data;
}
