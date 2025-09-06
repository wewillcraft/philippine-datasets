import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, _ctx) {
    try {
      const regions = await runQuery(`
        MATCH (r:Region)
        RETURN r.psgc_code as psgc_code, 
               r.name as name,
               r.population_2020 as population_2020
        ORDER BY r.psgc_code
      `);
      return Response.json({ 
        data: regions,
        count: regions.length 
      });
    } catch (error) {
      console.error("Error fetching regions:", error);
      return Response.json(
        { error: "Failed to fetch regions", details: error instanceof Error ? error.message : String(error) },
        { status: 500 }
      );
    }
  },
};