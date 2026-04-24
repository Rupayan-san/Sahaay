import axios from 'axios';
import toast from 'react-hot-toast';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const actorId = localStorage.getItem('actorId') ?? '';
  const actorRole = localStorage.getItem('actorRole') ?? 'admin';

  config.headers = config.headers ?? {};

  if (actorId) {
    config.headers['X-Actor-Id'] = actorId;
  }
  config.headers['X-Actor-Role'] = actorRole;

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
        toast.error('Unable to reach the backend. Check that the FastAPI server is running.');
      }
    } else {
      toast.error('An unexpected error occurred.');
    }

    return Promise.reject(error);
  },
);

export default apiClient;
