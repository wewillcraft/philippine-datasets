import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, _ctx) {
    try {
      await runQuery(`
        MATCH (n)
        RETURN count(n) as nodeCount
        LIMIT 1
      `);
      return Response.json({
        status: "ok",
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      return Response.json(
        {
          status: "error",
          timestamp: new Date().toISOString(),
        },
        { status: 503 },
      );
    }
  },
};
