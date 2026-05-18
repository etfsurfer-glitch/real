import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!url || !key) {
  // eslint-disable-next-line no-console
  console.error("VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY missing");
}

export const supabase = createClient(url, key, {
  auth: { persistSession: false },
});

export const TRADE_LABEL: Record<string, string> = {
  A1: "매매",
  B1: "전세",
  B2: "월세",
};
