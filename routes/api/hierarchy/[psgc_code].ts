import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      const hierarchy = await runQuery(`
        MATCH (target {psgc_code: $psgc_code})
        MATCH (r:Region)
        MATCH path = shortestPath((r)-[*0..4]->(target))
        WITH nodes(path) as pathNodes
        UNWIND pathNodes as node
        WITH node,
             CASE 
               WHEN 'Region' IN labels(node) THEN 0
               WHEN 'Province' IN labels(node) THEN 1
               WHEN 'CityMunicipality' IN labels(node) THEN 2
               WHEN 'Barangay' IN labels(node) THEN 3
               WHEN 'SubMunicipality' IN labels(node) THEN 3
             END as sortOrder
        ORDER BY sortOrder
        RETURN labels(node)[0] as type,
               node.psgc_code as psgc_code,
               node.name as name,
               node.population_2020 as population,
               node.city_class as city_class,
               node.income_classification as income_classification,
               node.urban_rural as urban_rural
      `, { psgc_code });

      if (!hierarchy || hierarchy.length === 0) {
        return Response.json(
          { error: "Location not found" },
          { status: 404 }
        );
      }

      return Response.json({ 
        psgc_code,
        hierarchy 
      });
    } catch (error) {
      return Response.json(
        { error: "Failed to fetch hierarchy" },
        { status: 500 }
      );
    }
  },
};