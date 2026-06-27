import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach authentication token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('alphamatrix_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      if (status === 401) {
        localStorage.removeItem('alphamatrix_token');
        window.dispatchEvent(new CustomEvent('auth:expired'));
      }
      if (status === 429) {
        window.dispatchEvent(new CustomEvent('rate:limited'));
      }
      return Promise.reject({ status, detail: error.response.data?.detail || `Request failed with status ${status}` });
    }
    if (error.code === 'ECONNABORTED') {
      return Promise.reject({ detail: 'Request timed out. The backend may be overloaded.' });
    }
    return Promise.reject({ detail: 'Network error. Please check your backend connection.' });
  }
);

export default apiClient;
