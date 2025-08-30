import { auth } from './firebase';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: any) {
    super(message);
    this.name = 'ApiError';
  }
}

async function getAuthToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;

  try {
    return await user.getIdToken();
  } catch (error) {
    console.error('Error getting auth token:', error);
    return null;
  }
}

async function makeAuthenticatedRequest(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = await getAuthToken();

  const headers: HeadersInit = {
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: response.statusText };
    }

    throw new ApiError(
      response.status,
      errorData.detail || errorData.message || 'An error occurred',
      errorData
    );
  }

  return response;
}

export async function uploadTaskZip(file: File): Promise<any> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await makeAuthenticatedRequest('/upload-task', {
    method: 'POST',
    body: formData,
  });

  return response.json();
}

export async function getApiHealth(): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/`);
  return response.json();
}

// Generic authenticated GET request
export async function apiGet(endpoint: string): Promise<any> {
  const response = await makeAuthenticatedRequest(endpoint, {
    method: 'GET',
  });
  return response.json();
}

// Generic authenticated POST request
export async function apiPost(endpoint: string, data?: any): Promise<any> {
  const headers: HeadersInit = {};
  let body: string | FormData | undefined;

  if (data instanceof FormData) {
    body = data;
  } else if (data) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(data);
  }

  const response = await makeAuthenticatedRequest(endpoint, {
    method: 'POST',
    headers,
    body,
  });

  return response.json();
}

// Generic authenticated PUT request
export async function apiPut(endpoint: string, data?: any): Promise<any> {
  const response = await makeAuthenticatedRequest(endpoint, {
    method: 'PUT',
    headers: data ? { 'Content-Type': 'application/json' } : {},
    body: data ? JSON.stringify(data) : undefined,
  });

  return response.json();
}

// Generic authenticated DELETE request
export async function apiDelete(endpoint: string): Promise<any> {
  const response = await makeAuthenticatedRequest(endpoint, {
    method: 'DELETE',
  });

  // Handle empty responses
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}
