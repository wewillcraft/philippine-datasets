import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, _ctx) {
    try {
      const provinces = await runQuery(`
        MATCH (p:Province)
        OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
        RETURN p.psgc_code as psgc_code, 
               p.name as name,
               p.population_2020 as population_2020,
               r.psgc_code as region_code,
               r.name as region_name
        ORDER BY p.psgc_code
      `);
      return Response.json({ 
        data: provinces,
        count: provinces.length 
      });
    } catch (error) {
      console.error("Error fetching provinces:", error);
      return Response.json(
        { error: "Failed to fetch provinces", details: error instanceof Error ? error.message : String(error) },
        { status: 500 }
      );
    }
  },
};