// Thin fetch client for the backend API.

import type { DatasetManifest } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

async function getJSON<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  dataSummary: () => getJSON<DatasetManifest>("/health/data"),
};
