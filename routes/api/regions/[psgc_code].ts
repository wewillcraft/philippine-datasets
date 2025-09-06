import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      const regionData = await runQuery(`
        MATCH (r:Region {psgc_code: $psgc_code})
        OPTIONAL MATCH (r)-[:HAS_PROVINCE]->(p:Province)
        OPTIONAL MATCH (r)-[:HAS_CITY_MUNICIPALITY]->(c:CityMunicipality)
        RETURN r as region,
               collect(DISTINCT p) as provinces,
               collect(DISTINCT c) as cities
      `, { psgc_code });

      if (!regionData || regionData.length === 0) {
        return Response.json(
          { error: "Region not found" },
          { status: 404 }
        );
      }

      const result = regionData[0];
      const provinces = result.provinces.filter((p: any) => p);
      const cities = result.cities.filter((c: any) => c);
      return Response.json({
        region: result.region,
        provinces: provinces,
        cities: cities,
        count: {
          provinces: provinces.length,
          cities: cities.length
        }
      });
    } catch (error) {
      return Response.json(
        { error: "Failed to fetch region details" },
        { status: 500 }
      );
    }
  },
};