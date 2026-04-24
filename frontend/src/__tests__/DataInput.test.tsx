import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const mockNavigate = jest.fn();
const mockIngestAndCreateIssue = jest.fn();

jest.mock('react-router-dom', () => {
  const actual = jest.requireActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

jest.mock('../api/issues', () => ({
  ingestAndCreateIssue: (...args: unknown[]) => mockIngestAndCreateIssue(...args),
}));

const { DataInput } = require('../pages/DataInput');

function renderDataInput() {
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
        <DataInput />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('DataInput', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockIngestAndCreateIssue.mockReset();
  });

  test('text tab submission shows loading state and navigates on success', async () => {
    let resolveRequest:
      | ((value: {
          ingestResult: {
            success: boolean;
            data: {
              content: string;
              source_type: string;
              metadata: Record<string, never>;
              location: string;
              timestamp: string;
            };
          };
          issue: {
            issue_id: string;
            title: string;
            category: string;
            location: string;
            severity: string;
            description: string;
            report_count: number;
            priority_score: number;
            status: string;
            created_at: string;
            updated_at: string;
          };
          matched_existing: boolean;
        }) => void)
      | undefined;

    mockIngestAndCreateIssue.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );

    renderDataInput();

    await userEvent.type(
      screen.getByLabelText(/raw description/i),
      'Water pump broken at Village A and nearby residents are affected.',
    );
    await userEvent.type(screen.getByLabelText(/location/i), 'Village A');
    await userEvent.click(screen.getByRole('button', { name: /process text report/i }));

    expect(
      await screen.findByText(/processing the report and extracting issue details/i),
    ).toBeInTheDocument();

    expect(mockIngestAndCreateIssue.mock.calls[0]?.[0]).toEqual({
      type: 'text',
      text: 'Water pump broken at Village A and nearby residents are affected.\nLocation: Village A',
    });

    resolveRequest?.({
      ingestResult: {
        success: true,
        data: {
          content: 'Water pump broken at Village A',
          source_type: 'form',
          metadata: {},
          location: 'Village A',
          timestamp: new Date().toISOString(),
        },
      },
      issue: {
        issue_id: 'new-issue-id',
        title: 'Water pump broken',
        category: 'water',
        location: 'Village A',
        severity: 'high',
        description: 'Main pump is broken',
        report_count: 1,
        priority_score: 75,
        status: 'open',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      matched_existing: false,
    });

    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith(
        '/extraction',
        expect.objectContaining({
          state: expect.objectContaining({
            matched_existing: false,
          }),
        }),
      ),
    );
  });

  test('submit button is disabled when the text is too short', async () => {
    renderDataInput();

    await userEvent.type(screen.getByLabelText(/raw description/i), 'ab');
    await userEvent.type(screen.getByLabelText(/location/i), 'Village A');

    expect(screen.getByRole('button', { name: /process text report/i })).toBeDisabled();
  });

  test('tab switching shows image and audio upload inputs', async () => {
    renderDataInput();

    await userEvent.click(screen.getByRole('button', { name: /upload image/i }));
    expect(screen.getByLabelText(/image upload/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /upload audio/i }));
    expect(screen.getByLabelText(/audio upload/i)).toBeInTheDocument();
  });
});
