import { rest } from 'msw';

const now = new Date().toISOString();

export const handlers = [
  rest.get('http://localhost:8000/api/issues', (_req, res, ctx) => {
    return res(
      ctx.json({
        data: [
          {
            issue_id: 'mock-issue-1',
            title: 'Water pump broken',
            category: 'water',
            location: 'Village A',
            severity: 'high',
            description: 'Main pump is broken',
            report_count: 3,
            priority_score: 80,
            status: 'open',
            created_at: now,
            updated_at: now,
          },
        ],
      }),
    );
  }),

  rest.post('http://localhost:8000/api/ingest', async (_req, res, ctx) => {
    return res(
      ctx.json({
        success: true,
        data: {
          content: 'Water pump broken at Village A',
          source_type: 'form',
          metadata: {},
          location: 'Village A',
          timestamp: now,
        },
      }),
    );
  }),

  rest.post('http://localhost:8000/api/issues', (_req, res, ctx) => {
    return res(
      ctx.json({
        matched_existing: false,
        similarity: 0,
        data: {
          issue_id: 'new-issue-id',
          title: 'Water pump broken',
          category: 'water',
          location: 'Village A',
          severity: 'high',
          description: 'Main pump is broken',
          report_count: 1,
          priority_score: 75,
          status: 'open',
          created_at: now,
          updated_at: now,
        },
      }),
    );
  }),

  rest.get('http://localhost:8000/api/leaderboard', (_req, res, ctx) => {
    return res(
      ctx.json({
        leaderboard: [
          {
            rank: 1,
            volunteer_id: 'v1',
            name: 'Alice',
            points: 450,
            trust_score: 92,
            tasks_completed: 45,
            badges: ['Expert'],
          },
        ],
      }),
    );
  }),

  rest.get('http://localhost:8000/api/reports/dashboard', (_req, res, ctx) => {
    return res(
      ctx.json({
        active_issues: 5,
        pending_assignments: 2,
        volunteers_active: 12,
        avg_trust_score: 73,
        issues_resolved_today: 3,
        high_priority_open: 1,
      }),
    );
  }),
];
