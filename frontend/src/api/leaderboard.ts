import apiClient from './client';
import type { LeaderboardCategory, LeaderboardEntry, LeaderboardTimeframe } from '../types';

export async function getLeaderboard(params?: {
  category?: LeaderboardCategory;
  timeframe?: LeaderboardTimeframe;
  limit?: number;
}): Promise<{ leaderboard: LeaderboardEntry[] }> {
  const response = await apiClient.get<{ leaderboard: LeaderboardEntry[] }>('/api/leaderboard', {
    params,
  });
  return response.data;
}
