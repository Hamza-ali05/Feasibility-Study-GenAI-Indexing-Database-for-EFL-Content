import axios from "axios";
import { TOKEN_KEY, clearToken } from "services/authStorage";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (typeof FormData !== "undefined" && config.data instanceof FormData) {
      delete config.headers["Content-Type"];
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      clearToken();
      const path = window.location.pathname || "";
      if (!path.includes("/authentication/sign-in")) {
        window.location.assign("/authentication/sign-in");
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
export { API_URL };
