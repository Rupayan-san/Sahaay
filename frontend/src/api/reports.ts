import apiClient from './client';
import type { DashboardStats, IssueTrend, VolunteerPerformanceReport } from '../types';

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await apiClient.get<DashboardStats>('/api/reports/dashboard');
  return response.data;
}

export async function getTrends(days?: number, category?: string): Promise<IssueTrend> {
  const response = await apiClient.get<IssueTrend>('/api/reports/trends', {
    params: {
      ...(days ? { days } : {}),
      ...(category ? { category } : {}),
    },
  });
  return response.data;
}

export async function getVolunteerReport(volunteerId: string): Promise<VolunteerPerformanceReport> {
  const response = await apiClient.get<VolunteerPerformanceReport>(`/api/volunteers/${volunteerId}/report`);
  return response.data;
}
