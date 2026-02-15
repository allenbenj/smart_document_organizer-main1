const BASE_URL = import.meta.env.VITE_API_BASE_URL || window.location.origin;

export async function api<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const defaultHeaders = { 'Content-Type': 'application/json' };
  const config: RequestInit = {
    headers: { ...defaultHeaders, ...options.headers },
    ...options,
  };

  let lastError: Error;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const response = await fetch(url, config);
      if (!response.ok) {
        let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const body = await response.json();
          errorMsg = body.detail || body.error || errorMsg;
        } catch {
          // If JSON parse fails, use status text
        }
        throw new Error(`Server error: ${errorMsg}`);
      }
      let data: T;
      try {
        data = await response.json();
      } catch {
        throw new Error('Invalid response: server returned non-JSON data');
      }
      return data;
    } catch (error) {
      lastError = error as Error;
      if (error instanceof TypeError && (error.message.includes('fetch') || error.message.includes('NetworkError'))) {
        // Network error, retry
        if (attempt < 3) {
          await new Promise(resolve => setTimeout(resolve, 1000 * attempt)); // Exponential backoff
          continue;
        } else {
          throw new Error('Network error: unable to connect to server. Check your internet connection or server status.');
        }
      } else {
        // Other errors, like server errors, don't retry
        throw error;
      }
    }
  }
  throw lastError!;
}