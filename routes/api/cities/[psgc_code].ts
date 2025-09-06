import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      const cityData = await runQuery(`
        MATCH (c:CityMunicipality {psgc_code: $psgc_code})
        OPTIONAL MATCH (c)-[:HAS_BARANGAY]->(b:Barangay)
        OPTIONAL MATCH (c)-[:HAS_SUBMUNICIPALITY]->(s:SubMunicipality)
        RETURN c as city,
               collect(DISTINCT b) as barangays,
               collect(DISTINCT s) as submuns
      `, { psgc_code });

      if (!cityData || cityData.length === 0) {
        return Response.json(
          { error: "City/Municipality not found" },
          { status: 404 }
        );
      }

      const result = cityData[0];
      const barangays = result.barangays.filter((b: any) => b);
      const submunicipalities = result.submuns.filter((s: any) => s);
      return Response.json({
        city: result.city,
        barangays: barangays,
        submunicipalities: submunicipalities,
        count: {
          barangays: barangays.length,
          submunicipalities: submunicipalities.length
        }
      });
    } catch (error) {
      return Response.json(
        { error: "Failed to fetch city details" },
        { status: 500 }
      );
    }
  },
};