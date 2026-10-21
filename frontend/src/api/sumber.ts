import { httpApi } from "./client.ts";
import type { SihalalApi } from "./client.ts";
import { mockApi } from "../mocks/mockApi.ts";

export const apiMode = import.meta.env.VITE_API_MODE === "http" ? "http" : "mock";

/** Pilih sumber data lewat VITE_API_MODE di .env.development. */
export const api: SihalalApi = apiMode === "http" ? httpApi : mockApi;
