import { createClient, type SupabaseClient } from "@supabase/supabase-js";

// In dev (and in PWA local-only mode), set VITE_API_BASE to point at
// scripts/local_api.py — the frontend then talks to SQLite directly through
// a tiny shim that implements only the supabase-js methods our pages use.
// In production (or whenever VITE_API_BASE is empty), the real Supabase client
// is used.
const apiBase = import.meta.env.VITE_API_BASE;

type Filter = { op: "eq" | "in" | "ilike"; col: string; val: unknown };

class LocalBuilder<T = unknown> implements PromiseLike<{ data: T; error: unknown }> {
  private _table: string;
  private _select = "*";
  private _filters: Filter[] = [];
  private _order: { col: string; ascending: boolean } | null = null;
  private _limit: number | null = null;
  private _single = false;

  constructor(table: string) {
    this._table = table;
  }
  select(cols: string) {
    this._select = cols;
    return this;
  }
  eq(col: string, val: unknown) {
    this._filters.push({ op: "eq", col, val });
    return this;
  }
  in(col: string, val: unknown[]) {
    this._filters.push({ op: "in", col, val });
    return this;
  }
  ilike(col: string, val: string) {
    this._filters.push({ op: "ilike", col, val });
    return this;
  }
  order(col: string, opts?: { ascending?: boolean }) {
    this._order = { col, ascending: opts?.ascending ?? true };
    return this;
  }
  limit(n: number) {
    this._limit = n;
    return this;
  }
  single() {
    this._single = true;
    return this;
  }

  async then<TResult1 = { data: T; error: unknown }, TResult2 = never>(
    onfulfilled?: ((v: { data: T; error: unknown }) => TResult1 | PromiseLike<TResult1>) | null,
    onrejected?: ((reason: unknown) => TResult2 | PromiseLike<TResult2>) | null,
  ): Promise<TResult1 | TResult2> {
    try {
      const res = await fetch(`${apiBase}/q`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          table: this._table,
          select: this._select,
          filters: this._filters,
          order: this._order,
          limit: this._limit,
          single: this._single,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        const out = { data: null as unknown as T, error: { message: `HTTP ${res.status}: ${text}` } };
        return onfulfilled ? onfulfilled(out) : (out as unknown as TResult1);
      }
      const j = (await res.json()) as { data: T; error: unknown };
      return onfulfilled ? onfulfilled(j) : (j as unknown as TResult1);
    } catch (e: unknown) {
      const out = { data: null as unknown as T, error: e };
      if (onrejected) return onrejected(e);
      return onfulfilled ? onfulfilled(out) : (out as unknown as TResult1);
    }
  }
}

const localClient = {
  from: (table: string) => new LocalBuilder(table),
};

let client: unknown;
if (apiBase) {
  client = localClient;
  // eslint-disable-next-line no-console
  console.info(`[supabase] local API mode → ${apiBase}`);
} else {
  const url = import.meta.env.VITE_SUPABASE_URL;
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY;
  if (!url || !key) {
    // eslint-disable-next-line no-console
    console.error("VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY missing");
  }
  client = createClient(url, key, { auth: { persistSession: false } });
}

// In stub mode we present the local client as a SupabaseClient so the
// frontend's existing row-shape inference (from .select("col1, col2, ...") )
// keeps working. The runtime methods we implement are a strict subset of
// what the pages actually call.
export const supabase = client as SupabaseClient;

export const TRADE_LABEL: Record<string, string> = {
  A1: "매매",
  B1: "전세",
  B2: "월세",
};
