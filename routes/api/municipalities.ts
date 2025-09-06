import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, _ctx) {
    try {
      const municipalities = await runQuery(`
        MATCH (m:CityMunicipality {type: 'municipality'})
        OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(m)
        OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
        OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(m)
        WITH m, p, COALESCE(r, r2) as region
        RETURN m.psgc_code as psgc_code, 
               m.name as name,
               m.income_classification as income_classification,
               m.population_2020 as population_2020,
               p.psgc_code as province_code,
               p.name as province_name,
               region.psgc_code as region_code,
               region.name as region_name
        ORDER BY m.psgc_code
      `);
      return Response.json({
        data: municipalities,
        count: municipalities.length,
      });
    } catch (error) {
      console.error("Error fetching municipalities:", error);
      return Response.json(
        {
          error: "Failed to fetch municipalities",
          details: error instanceof Error ? error.message : String(error),
        },
        { status: 500 },
      );
    }
  },
};
