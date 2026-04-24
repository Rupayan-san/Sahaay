import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the dashboard landing experience', async () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );

  expect(
    await screen.findByText(/watch the highest-risk issues and volunteer momentum in one view/i),
  ).toBeInTheDocument();
});
