import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      const provinceData = await runQuery(`
        MATCH (p:Province {psgc_code: $psgc_code})
        OPTIONAL MATCH (p)-[:HAS_CITY_MUNICIPALITY]->(c:CityMunicipality)
        RETURN p as province,
               collect(c) as cities
      `, { psgc_code });

      if (!provinceData || provinceData.length === 0) {
        return Response.json(
          { error: "Province not found" },
          { status: 404 }
        );
      }

      const result = provinceData[0];
      const cities = result.cities.filter((c: any) => c);
      return Response.json({
        province: result.province,
        cities: cities,
        count: cities.length
      });
    } catch (error) {
      return Response.json(
        { error: "Failed to fetch province details" },
        { status: 500 }
      );
    }
  },
};