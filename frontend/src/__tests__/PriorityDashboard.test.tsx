import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PriorityDashboard } from '../pages/PriorityDashboard';

function renderPriorityDashboard() {
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
        <PriorityDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('PriorityDashboard', () => {
  test('renders dashboard stats', async () => {
    renderPriorityDashboard();

    expect(await screen.findByText('5')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  test('leaderboard renders the top volunteer', async () => {
    renderPriorityDashboard();

    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
  });
});
