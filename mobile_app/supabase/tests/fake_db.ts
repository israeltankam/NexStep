/** In-memory PostgREST-shaped query double for API authorization/page tests. */

import type { JsonObject, SessionContext } from "../functions/nexstep-mobile-api/_shared/types.ts";

export interface QueryTrace {
  table: string;
  filters: Array<[string, unknown]>;
  range: [number, number] | null;
}

export class FakeDb {
  readonly calls: QueryTrace[] = [];
  readonly rpcs: Array<{ name: string; args: JsonObject }> = [];
  rpcError: { code: string; message: string } | null = null;

  constructor(private readonly tables: Record<string, JsonObject[]>) {}

  from(table: string) {
    const trace: QueryTrace = { table, filters: [], range: null };
    this.calls.push(trace);
    const ordering: Array<{ column: string; ascending: boolean }> = [];
    let limit: number | null = null;
    const query = {
      select: (_columns: string) => query,
      eq: (column: string, value: unknown) => {
        trace.filters.push([column, value]);
        return query;
      },
      not: (column: string, _operator: string, value: unknown) => {
        trace.filters.push([column, { not: value }]);
        return query;
      },
      in: (column: string, values: unknown[]) => {
        trace.filters.push([column, { in: values }]);
        return query;
      },
      order: (column: string, options: { ascending: boolean }) => {
        ordering.push({ column, ascending: options.ascending });
        return query;
      },
      range: (first: number, last: number) => {
        trace.range = [first, last];
        return query;
      },
      limit: (count: number) => {
        limit = count;
        return query;
      },
      then: <T>(resolve: (value: { data: JsonObject[]; error: null }) => T) => {
        let data = [...(this.tables[table] ?? [])];
        for (const [column, expected] of trace.filters) {
          data = data.filter((row) => {
            if (expected && typeof expected === "object" && "in" in expected) {
              return (expected.in as unknown[]).includes(row[column]);
            }
            if (expected && typeof expected === "object" && "not" in expected) {
              return row[column] !== expected.not;
            }
            return row[column] === expected;
          });
        }
        for (const { column, ascending } of [...ordering].reverse()) {
          data.sort((left, right) => String(left[column] ?? "").localeCompare(
            String(right[column] ?? "")) * (ascending ? 1 : -1));
        }
        if (trace.range) data = data.slice(trace.range[0], trace.range[1] + 1);
        if (limit !== null) data = data.slice(0, limit);
        return Promise.resolve({ data, error: null }).then(resolve);
      },
    };
    return query;
  }

  rpc(name: string, args: JsonObject) {
    this.rpcs.push({ name, args });
    return Promise.resolve(this.rpcError
      ? { data: null, error: this.rpcError }
      : { data: { ok: true }, error: null });
  }

  context(role: string, global = false): SessionContext {
    return {
      db: this as unknown as SessionContext["db"], sessionId: "session",
      organization: { id: "org-a" },
      user: { id: "user-admin", is_global_admin: global },
      orgUser: { id: "link-admin", role },
    };
  }
}
