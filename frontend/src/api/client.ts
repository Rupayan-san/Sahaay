import axios from 'axios';
import toast from 'react-hot-toast';
// Force store initialization before first render
import '../store/useAppStore';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const actorId = localStorage.getItem('actorId') ?? '';
  const actorRole = localStorage.getItem('actorRole') ?? 'admin';
  const DEFAULT_ADMIN_ID = '3b0d4d88-2f30-4e97-81d3-2bb8d0a55a11';

  config.headers = config.headers ?? {};

  config.headers['X-Actor-Id'] = config.headers['X-Actor-Id'] ?? (actorId || DEFAULT_ADMIN_ID);
  config.headers['X-Actor-Role'] = config.headers['X-Actor-Role'] ?? actorRole;

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error)) {
      if (error.response) {
        const detail = error.response.data?.detail;
        const message =
          typeof detail === 'string'
            ? detail
            : detail
              ? JSON.stringify(detail)
            : error.message || 'Request failed';
        toast.error(message);
      } else {
        const method = error.config?.method?.toLowerCase();
        if (method !== 'get') {
          toast.error('Unable to reach the backend. Check that the FastAPI server is running.');
        }
      }
    } else {
      toast.error('An unexpected error occurred.');
    }

    return Promise.reject(error);
  },
);

export default apiClient;
