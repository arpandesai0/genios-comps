import type { ApiErrorBody } from "./api-types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public details: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = await response.json();
  if (!response.ok) {
    const error = (body as ApiErrorBody).error;
    throw new ApiError(
      error?.message ?? `Request failed (${response.status})`,
      response.status,
      error?.details ?? {},
    );
  }
  return body as T;
}
