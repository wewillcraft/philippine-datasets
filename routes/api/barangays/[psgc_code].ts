import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      const barangayData = await runQuery(
        `
        MATCH (b:Barangay {psgc_code: $psgc_code})
        OPTIONAL MATCH (c:CityMunicipality)-[:HAS_BARANGAY]->(b)
        OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(c)
        OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
        OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(c)
        RETURN b as barangay,
               c as city,
               COALESCE(p, r2) as province,
               COALESCE(r, r2) as region
      `,
        { psgc_code },
      );

      if (!barangayData || barangayData.length === 0) {
        return Response.json(
          { error: "Barangay not found" },
          { status: 404 },
        );
      }

      const result = barangayData[0];
      return Response.json({
        barangay: result.barangay,
        city: result.city,
        province: result.province,
        region: result.region,
      });
    } catch (error) {
      return Response.json(
        { error: "Failed to fetch barangay details" },
        { status: 500 },
      );
    }
  },
};
