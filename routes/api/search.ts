import { Handlers } from "$fresh/server.ts";
import { neo4j, runQuery } from "../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(req, _ctx) {
    const url = new URL(req.url);
    const query = url.searchParams.get("q");
    const limit = Math.floor(parseInt(url.searchParams.get("limit") || "100"));
    const offset = Math.floor(parseInt(url.searchParams.get("offset") || "0"));
    const sort = url.searchParams.get("sort") || "name";
    const type = url.searchParams.get("type");

    if (!query) {
      return Response.json(
        { error: "Query parameter 'q' is required" },
        { status: 400 },
      );
    }

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

    const orderByField = sort === "population" ? "population DESC" : sort;

    try {
      let typeConditions = "";
      let countTypeConditions = "";

      if (type) {
        const validTypes = [
          "region",
          "province",
          "city",
          "municipality",
          "barangay",
        ];
        const typeFilter = type.toLowerCase();

        if (!validTypes.includes(typeFilter)) {
          return Response.json(
            {
              error:
                "Invalid type parameter. Must be one of: region, province, city, municipality, barangay",
            },
            { status: 400 },
          );
        }

        if (typeFilter === "region") {
          typeConditions = `
            MATCH (r:Region)
            WHERE toLower(r.name) CONTAINS toLower($query)
            RETURN 'Region' as type, r.psgc_code as psgc_code, r.name as name, r.population_2020 as population
          `;
          countTypeConditions = `
            MATCH (r:Region)
            WHERE toLower(r.name) CONTAINS toLower($query)
            RETURN r
          `;
        } else if (typeFilter === "province") {
          typeConditions = `
            MATCH (p:Province)
            WHERE toLower(p.name) CONTAINS toLower($query)
            RETURN 'Province' as type, p.psgc_code as psgc_code, p.name as name, p.population_2020 as population
          `;
          countTypeConditions = `
            MATCH (p:Province)
            WHERE toLower(p.name) CONTAINS toLower($query)
            RETURN p
          `;
        } else if (typeFilter === "city" || typeFilter === "municipality") {
          const cityType = typeFilter === "city" ? "CITY" : "MUNICIPALITY";
          typeConditions = `
            MATCH (c:CityMunicipality)
            WHERE toLower(c.name) CONTAINS toLower($query) AND c.city_municipality = '${cityType}'
            RETURN 'City/Municipality' as type, c.psgc_code as psgc_code, c.name as name, c.population_2020 as population
          `;
          countTypeConditions = `
            MATCH (c:CityMunicipality)
            WHERE toLower(c.name) CONTAINS toLower($query) AND c.city_municipality = '${cityType}'
            RETURN c
          `;
        } else if (typeFilter === "barangay") {
          typeConditions = `
            MATCH (b:Barangay)
            WHERE toLower(b.name) CONTAINS toLower($query)
            RETURN 'Barangay' as type, b.psgc_code as psgc_code, b.name as name, b.population_2020 as population
          `;
          countTypeConditions = `
            MATCH (b:Barangay)
            WHERE toLower(b.name) CONTAINS toLower($query)
            RETURN b
          `;
        }

        const results = await runQuery(
          `
          ${typeConditions}
          ORDER BY ${orderByField}
          SKIP $offset
          LIMIT $limit
        `,
          { query, limit: neo4j.int(limit), offset: neo4j.int(offset) },
        );

        const countResult = await runQuery(
          `
          ${countTypeConditions}
          RETURN count(*) as total
        `,
          { query },
        );

        return Response.json({
          query,
          type: typeFilter,
          sort,
          data: results,
          count: results.length,
          pagination: {
            limit,
            offset,
            total: countResult[0]?.total || 0,
          },
        });
      } else {
        const results = await runQuery(
          `
          CALL {
            MATCH (r:Region)
            WHERE toLower(r.name) CONTAINS toLower($query)
            RETURN 'Region' as type, r.psgc_code as psgc_code, r.name as name, r.population_2020 as population
            UNION
            MATCH (p:Province)
            WHERE toLower(p.name) CONTAINS toLower($query)
            RETURN 'Province' as type, p.psgc_code as psgc_code, p.name as name, p.population_2020 as population
            UNION
            MATCH (c:CityMunicipality)
            WHERE toLower(c.name) CONTAINS toLower($query)
            RETURN 'City/Municipality' as type, c.psgc_code as psgc_code, c.name as name, c.population_2020 as population
            UNION
            MATCH (b:Barangay)
            WHERE toLower(b.name) CONTAINS toLower($query)
            RETURN 'Barangay' as type, b.psgc_code as psgc_code, b.name as name, b.population_2020 as population
          }
          RETURN type, psgc_code, name, population
          ORDER BY ${orderByField}
          SKIP $offset
          LIMIT $limit
        `,
          { query, limit: neo4j.int(limit), offset: neo4j.int(offset) },
        );

        const countResult = await runQuery(
          `
          CALL {
            MATCH (r:Region)
            WHERE toLower(r.name) CONTAINS toLower($query)
            RETURN r as node
            UNION
            MATCH (p:Province)
            WHERE toLower(p.name) CONTAINS toLower($query)
            RETURN p as node
            UNION
            MATCH (c:CityMunicipality)
            WHERE toLower(c.name) CONTAINS toLower($query)
            RETURN c as node
            UNION
            MATCH (b:Barangay)
            WHERE toLower(b.name) CONTAINS toLower($query)
            RETURN b as node
          }
          RETURN count(*) as total
        `,
          { query },
        );

        return Response.json({
          query,
          sort,
          data: results,
          count: results.length,
          pagination: {
            limit,
            offset,
            total: countResult[0]?.total || 0,
          },
        });
      }
    } catch (error) {
      return Response.json(
        {
          error: "Search failed",
          details: error instanceof Error ? error.message : String(error),
        },
        { status: 500 },
      );
    }
  },
};
