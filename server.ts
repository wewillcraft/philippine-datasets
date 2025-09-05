import { Application, Router } from "oak";
import { load } from "dotenv";
import { runQuery } from "./lib/neo4j.ts";

// Load environment variables
await load({ export: true });

const app = new Application();
const router = new Router();

// Load HTML template at startup
const indexTemplate = await Deno.readTextFile("./templates/index.html");

router.get("/", async (ctx) => {
  // Get some statistics for the landing page
  let stats = { regions: 0, provinces: 0, cities: 0, municipalities: 0, barangays: 0 };
  try {
    const counts = await runQuery(`
      MATCH (r:Region) WITH count(r) as regions
      MATCH (p:Province) WITH regions, count(p) as provinces
      MATCH (c:CityMunicipality) 
      WITH regions, provinces, 
           count(CASE WHEN c.type = 'city' THEN 1 END) as cities,
           count(CASE WHEN c.type = 'municipality' THEN 1 END) as municipalities
      MATCH (b:Barangay) 
      RETURN regions, provinces, cities, municipalities, count(b) as barangays
    `);
    if (counts && counts[0]) {
      stats = counts[0];
    }
  } catch (error) {
    console.error("Error fetching stats:", error);
  }

  // Replace template variables
  let html = indexTemplate
    .replace("{{regions}}", stats.regions.toLocaleString())
    .replace("{{provinces}}", stats.provinces.toLocaleString())
    .replace("{{cities}}", stats.cities.toLocaleString())
    .replace("{{municipalities}}", stats.municipalities.toLocaleString())
    .replace("{{barangays}}", stats.barangays.toLocaleString())
    .replace(/{{origin}}/g, ctx.request.url.origin);

  ctx.response.type = "text/html";
  ctx.response.body = html;
});

// Undocumented ping endpoint to keep Neo4j database active
router.get("/ping", async (ctx) => {
  try {
    // Run a simple query to keep the connection alive
    await runQuery(`
      MATCH (n)
      RETURN count(n) as nodeCount
      LIMIT 1
    `);
    ctx.response.body = { status: "ok", timestamp: new Date().toISOString() };
  } catch (error) {
    ctx.response.status = 503;
    ctx.response.body = { status: "error", timestamp: new Date().toISOString() };
  }
});

router.get("/regions", async (ctx) => {
  try {
    const regions = await runQuery(`
      MATCH (r:Region)
      RETURN r.psgc_code as psgc_code, 
             r.name as name,
             r.population_2020 as population_2020
      ORDER BY r.psgc_code
    `);
    ctx.response.body = { data: regions };
  } catch (error) {
    console.error("Error fetching regions:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch regions", details: error.message };
  }
});

router.get("/provinces", async (ctx) => {
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
    ctx.response.body = { data: provinces };
  } catch (error) {
    console.error("Error fetching provinces:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch provinces", details: error.message };
  }
});

router.get("/cities", async (ctx) => {
  try {
    const cities = await runQuery(`
      MATCH (c:CityMunicipality {type: 'city'})
      OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(c)
      OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
      OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(c)
      WITH c, p, COALESCE(r, r2) as region
      RETURN c.psgc_code as psgc_code, 
             c.name as name,
             c.city_class as city_class,
             c.income_classification as income_classification,
             c.population_2020 as population_2020,
             p.psgc_code as province_code,
             p.name as province_name,
             region.psgc_code as region_code,
             region.name as region_name
      ORDER BY c.psgc_code
    `);
    ctx.response.body = { data: cities };
  } catch (error) {
    console.error("Error fetching cities:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch cities", details: error.message };
  }
});

router.get("/municipalities", async (ctx) => {
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
    ctx.response.body = { data: municipalities };
  } catch (error) {
    console.error("Error fetching municipalities:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch municipalities", details: error.message };
  }
});

router.get("/localities", async (ctx) => {
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
    ctx.response.body = { data: localities };
  } catch (error) {
    console.error("Error fetching localities:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch localities", details: error.message };
  }
});

router.get("/barangays", async (ctx) => {
  const limit = parseInt(ctx.request.url.searchParams.get("limit") || "100");
  const offset = parseInt(ctx.request.url.searchParams.get("offset") || "0");
  
  try {
    const barangays = await runQuery(`
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
      ORDER BY b.psgc_code
      SKIP $offset
      LIMIT $limit
    `, { limit, offset });
    
    const count = await runQuery(`
      MATCH (b:Barangay)
      RETURN count(b) as total
    `);
    
    ctx.response.body = { 
      data: barangays,
      pagination: {
        limit,
        offset,
        total: count[0]?.total || 0
      }
    };
  } catch (error) {
    console.error("Error fetching barangays:", error);
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch barangays", details: error.message };
  }
});

router.get("/regions/:psgc_code", async (ctx) => {
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
      ctx.response.status = 404;
      ctx.response.body = { error: "Region not found" };
      return;
    }

    const result = regionData[0];
    ctx.response.body = {
      region: result.region,
      provinces: result.provinces.filter((p: any) => p),
      cities: result.cities.filter((c: any) => c)
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch region details" };
  }
});

router.get("/provinces/:psgc_code", async (ctx) => {
  const { psgc_code } = ctx.params;
  try {
    const provinceData = await runQuery(`
      MATCH (p:Province {psgc_code: $psgc_code})
      OPTIONAL MATCH (p)-[:HAS_CITY_MUNICIPALITY]->(c:CityMunicipality)
      RETURN p as province,
             collect(c) as cities
    `, { psgc_code });

    if (!provinceData || provinceData.length === 0) {
      ctx.response.status = 404;
      ctx.response.body = { error: "Province not found" };
      return;
    }

    const result = provinceData[0];
    ctx.response.body = {
      province: result.province,
      cities: result.cities.filter((c: any) => c)
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch province details" };
  }
});

router.get("/cities/:psgc_code", async (ctx) => {
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
      ctx.response.status = 404;
      ctx.response.body = { error: "City/Municipality not found" };
      return;
    }

    const result = cityData[0];
    ctx.response.body = {
      city: result.city,
      barangays: result.barangays.filter((b: any) => b),
      submunicipalities: result.submuns.filter((s: any) => s)
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch city details" };
  }
});

router.get("/barangays/:psgc_code", async (ctx) => {
  const { psgc_code } = ctx.params;
  try {
    const barangayData = await runQuery(`
      MATCH (b:Barangay {psgc_code: $psgc_code})
      OPTIONAL MATCH (c:CityMunicipality)-[:HAS_BARANGAY]->(b)
      OPTIONAL MATCH (p:Province)-[:HAS_CITY_MUNICIPALITY]->(c)
      OPTIONAL MATCH (r:Region)-[:HAS_PROVINCE]->(p)
      OPTIONAL MATCH (r2:Region)-[:HAS_CITY_MUNICIPALITY]->(c)
      RETURN b as barangay,
             c as city,
             COALESCE(p, r2) as province,
             COALESCE(r, r2) as region
    `, { psgc_code });

    if (!barangayData || barangayData.length === 0) {
      ctx.response.status = 404;
      ctx.response.body = { error: "Barangay not found" };
      return;
    }

    const result = barangayData[0];
    ctx.response.body = {
      barangay: result.barangay,
      city: result.city,
      province: result.province,
      region: result.region
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch barangay details" };
  }
});

router.get("/search", async (ctx) => {
  const query = ctx.request.url.searchParams.get("q");
  if (!query) {
    ctx.response.status = 400;
    ctx.response.body = { error: "Query parameter 'q' is required" };
    return;
  }

  try {
    const results = await runQuery(`
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
      ORDER BY type, name
      LIMIT 100
    `, { query });

    ctx.response.body = { 
      query,
      results,
      count: results.length
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Search failed" };
  }
});

router.get("/hierarchy/:psgc_code", async (ctx) => {
  const { psgc_code } = ctx.params;
  try {
    // Find the shortest path from any Region to the target location
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
      ctx.response.status = 404;
      ctx.response.body = { error: "Location not found" };
      return;
    }

    ctx.response.body = { 
      psgc_code,
      hierarchy 
    };
  } catch (error) {
    ctx.response.status = 500;
    ctx.response.body = { error: "Failed to fetch hierarchy" };
  }
});

app.use(async (ctx, next) => {
  ctx.response.headers.set("Access-Control-Allow-Origin", "*");
  ctx.response.headers.set("Access-Control-Allow-Methods", "GET, OPTIONS");
  ctx.response.headers.set("Access-Control-Allow-Headers", "Content-Type");
  
  if (ctx.request.method === "OPTIONS") {
    ctx.response.status = 200;
    return;
  }
  
  await next();
});

app.use(router.routes());
app.use(router.allowedMethods());

app.addEventListener("error", (evt) => {
  console.error("Server error:", evt.error);
});

const port = parseInt(Deno.env.get("PORT") || "8000");
console.log(`Server running on http://localhost:${port}`);
await app.listen({ port });