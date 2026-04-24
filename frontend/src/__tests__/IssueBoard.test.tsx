import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { rest } from 'msw';
import { server } from '../mocks/server';
import { IssueBoard } from '../pages/IssueBoard';

function renderIssueBoard() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <IssueBoard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('IssueBoard', () => {
  test('renders issue cards from API', async () => {
    renderIssueBoard();

    expect(await screen.findByText('Water pump broken')).toBeInTheDocument();
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByText('Village A')).toBeInTheDocument();
  });

  test('filter by category requests the selected category', async () => {
    let requestedCategory: string | null = null;

    server.use(
      rest.get('http://localhost:8000/api/issues', (req, res, ctx) => {
        requestedCategory = req.url.searchParams.get('category');
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
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
              },
            ],
          }),
        );
      }),
    );

    renderIssueBoard();
    await screen.findByText('Water pump broken');

    await userEvent.selectOptions(screen.getByRole('combobox', { name: /category/i }), 'water');

    await waitFor(() => expect(requestedCategory).toBe('water'));
  });

  test('empty state when no issues are returned', async () => {
    server.use(
      rest.get('http://localhost:8000/api/issues', (_req, res, ctx) => {
        return res(ctx.json({ data: [] }));
      }),
    );

    renderIssueBoard();

    expect(await screen.findByText('No issues match these filters')).toBeInTheDocument();
  });
});
