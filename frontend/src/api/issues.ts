import apiClient from './client';
import type {
  IngestResponse,
  Issue,
  IssueCategory,
  IssueStatus,
  IssueUpsertResponse,
} from '../types';

function parseStructuredText(rawText: string): { description: string; location?: string } {
  const lines = rawText
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  const locationLine = lines.find((line) => line.toLowerCase().startsWith('location:'));
  const descriptionLines = lines.filter((line) => !line.toLowerCase().startsWith('location:'));
  const description = descriptionLines.join('\n').trim();
  const location = locationLine?.split(':').slice(1).join(':').trim();

  return {
    description,
    location: location || undefined,
  };
}

export async function ingestAndCreateIssue(payload: {
  type: 'text' | 'image' | 'audio';
  text?: string;
  file?: File;
}): Promise<{ ingestResult: IngestResponse; issue: Issue; matched_existing: boolean }> {
  let ingestResult: IngestResponse;

  if (payload.type === 'text') {
    const text = payload.text?.trim();
    if (!text) {
      throw new Error('Please provide a text report.');
    }

    const { description, location } = parseStructuredText(text);
    const response = await apiClient.post<IngestResponse>('/api/ingest', {
      description,
      location,
    });
    ingestResult = response.data;
  } else {
    if (!payload.file) {
      throw new Error(`Please select a ${payload.type} file.`);
    }

    const formData = new FormData();
    formData.append('file', payload.file);

    const response = await apiClient.post<IngestResponse>('/api/ingest', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    ingestResult = response.data;
  }

  const issueResponse = await apiClient.post<IssueUpsertResponse>('/api/issues', {
    raw_text: ingestResult.data.content,
  });

  return {
    ingestResult,
    issue: issueResponse.data.data,
    matched_existing: issueResponse.data.matched_existing,
  };
}

export async function getIssues(params?: {
  limit?: number;
  skip?: number;
  status?: IssueStatus;
  category?: IssueCategory;
}): Promise<{ data: Issue[] }> {
  const response = await apiClient.get<{ data: Issue[] }>('/api/issues', {
    params,
  });
  return response.data;
}

export async function getIssue(issueId: string): Promise<{ data: Issue }> {
  try {
    const response = await apiClient.get<{ data: Issue }>(`/api/issues/${issueId}`);
    return response.data;
  } catch {
    const issueList = await getIssues({ limit: 100, skip: 0 });
    const issue = issueList.data.find((candidate) => candidate.issue_id === issueId);
    if (!issue) {
      throw new Error('Issue not found');
    }
    return { data: issue };
  }
}

export async function deleteIssue(issueId: string): Promise<void> {
  await apiClient.delete(`/api/issues/${issueId}`);
}
