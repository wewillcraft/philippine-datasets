import { Handlers } from "$fresh/server.ts";
import { neo4j, runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(req, _ctx) {
    const url = new URL(req.url);
    const limit = Math.floor(parseInt(url.searchParams.get("limit") || "100"));
    const offset = Math.floor(parseInt(url.searchParams.get("offset") || "0"));
    const sort = url.searchParams.get("sort") || "psgc_code";

    // Validate sort parameter
    const validSorts = ["psgc_code", "name", "population"];
    if (!validSorts.includes(sort)) {
      return Response.json(
        {
          error:
            "Invalid sort parameter. Must be one of: psgc_code, name, population",
        },
        { status: 400 },
      );
    }

    // Build ORDER BY clause
    const orderByField = sort === "population"
      ? "b.population_2020 DESC"
      : `b.${sort}`;

    try {
      const barangays = await runQuery(
        `
        MATCH (b:Barangay)
        OPTIONAL MATCH (c:CityMunicipality)-[:HAS_BARANGAY]->(b)
        OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(c)
        OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
        OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(c)
        WITH b, c, p, COALESCE(r, r2) as region
        RETURN b.psgc_code as psgc_code, 
               b.name as name,
               b.urban_rural as urban_rural,
               b.population_2020 as population_2020,
               c.psgc_code as city_code,
               c.name as city_name,
               p.psgc_code as province_code,
               p.name as province_name,
               region.psgc_code as region_code,
               region.name as region_name
        ORDER BY ${orderByField}
        SKIP $offset
        LIMIT $limit
      `,
        { limit: neo4j.int(limit), offset: neo4j.int(offset) },
      );

      const count = await runQuery(`
        MATCH (b:Barangay)
        RETURN count(b) as total
      `);

      return Response.json({
        data: barangays,
        count: barangays.length,
        pagination: {
          limit,
          offset,
          total: count[0]?.total || 0,
        },
      });
    } catch (error) {
      console.error("Error fetching barangays:", error);
      return Response.json(
        {
          error: "Failed to fetch barangays",
          details: error instanceof Error ? error.message : String(error),
        },
        { status: 500 },
      );
    }
  },
};
