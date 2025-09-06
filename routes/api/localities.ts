import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, _ctx) {
    try {
      const localities = await runQuery(`
        MATCH (c:CityMunicipality)
        OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(c)
        OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
        OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(c)
        WITH c, p, COALESCE(r, r2) as region
        RETURN c.psgc_code as psgc_code, 
               c.name as name,
               c.type as type,
               c.city_class as city_class,
               c.income_classification as income_classification,
               c.population_2020 as population_2020,
               p.psgc_code as province_code,
               p.name as province_name,
               region.psgc_code as region_code,
               region.name as region_name
        ORDER BY c.type DESC, c.psgc_code
      `);
      return Response.json({ 
        data: localities,
        count: localities.length 
      });
    } catch (error) {
      console.error("Error fetching localities:", error);
      return Response.json(
        { error: "Failed to fetch localities", details: error instanceof Error ? error.message : String(error) },
        { status: 500 }
      );
    }
  },
};