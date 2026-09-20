import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
});

// Attach the JWT to every request once the user has signed in.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("bi_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// A 401 means the session expired — send the user back to sign in.
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("bi_token");
      localStorage.removeItem("bi_user");
      if (!location.pathname.startsWith("/login")) location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const msg = (err, fallback = "Something went wrong.") =>
  err?.response?.data?.detail || err?.message || fallback;

// money/number helpers — used everywhere figures appear
export const rupees = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
export const compact = (n) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1e7) return "₹" + (v / 1e7).toFixed(2) + " Cr";
  if (Math.abs(v) >= 1e5) return "₹" + (v / 1e5).toFixed(2) + " L";
  return rupees(v);
};
export const count = (n) => Number(n || 0).toLocaleString("en-IN");
