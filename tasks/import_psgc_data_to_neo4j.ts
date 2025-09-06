import { load } from "dotenv";
import {
  clearDatabase,
  closeDriver,
  createIndexes,
  runQuery,
  runWrite,
} from "../src/neo4j.ts";
import type { PSGCData } from "../src/types.ts";

await load({ export: true });

const BATCH_SIZE = 500;

async function readJSONLFile(path: string): Promise<PSGCData[]> {
  const text = await Deno.readTextFile(path);
  return text
    .trim()
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
}

async function importBatch(
  items: PSGCData[],
  nodeType: string,
  properties: string[],
): Promise<void> {
  if (items.length === 0) return;

  const cypher = `
    UNWIND $items AS item
    CREATE (n:${nodeType})
    SET n = item
  `;

  const batchedItems = items.map((item) => {
    const filtered: Record<string, any> = {};
    properties.forEach((prop) => {
      if (
        item[prop as keyof PSGCData] !== null &&
        item[prop as keyof PSGCData] !== undefined
      ) {
        filtered[prop] = item[prop as keyof PSGCData];
      }
    });
    return filtered;
  });

  await runWrite(cypher, { items: batchedItems });
}

async function createRelationships(): Promise<void> {
  console.log("Creating relationships...");

  console.log("  Creating Region -> Province relationships...");
  await runWrite(`
    MATCH (r:Region)
    MATCH (p:Province)
    WHERE p.region_code = r.region_code 
      AND p.province_code <> '000'
      AND r.province_code = '000'
    CREATE (r)-[:HAS_PROVINCE]->(p)
  `);

  console.log("  Creating Province -> CityMunicipality relationships...");
  await runWrite(`
    MATCH (p:Province)
    MATCH (c:CityMunicipality)
    WHERE c.region_code = p.region_code 
      AND c.province_code = p.province_code
      AND p.municipality_code = '00'
      AND c.municipality_code <> '00'
    CREATE (p)-[:HAS_CITY_MUNICIPALITY]->(c)
  `);

  console.log("  Creating CityMunicipality -> Barangay relationships...");
  await runWrite(`
    MATCH (c:CityMunicipality)
    MATCH (b:Barangay)
    WHERE b.region_code = c.region_code 
      AND b.province_code = c.province_code
      AND b.municipality_code = c.municipality_code
      AND c.barangay_code = '000'
      AND b.barangay_code <> '000'
    CREATE (c)-[:HAS_BARANGAY]->(b)
  `);

  console.log(
    "  Creating CityMunicipality -> SubMunicipality relationships...",
  );
  await runWrite(`
    MATCH (c:CityMunicipality)
    MATCH (s:SubMunicipality)
    WHERE s.region_code = c.region_code 
      AND s.province_code = c.province_code
      AND s.municipality_code = c.municipality_code
    CREATE (c)-[:HAS_SUBMUNICIPALITY]->(s)
  `);

  console.log("  Handling NCR special case (Region acts as Province)...");
  await runWrite(`
    MATCH (r:Region {region_code: '13'})
    MATCH (c:CityMunicipality)
    WHERE c.region_code = '13'
    CREATE (r)-[:HAS_CITY_MUNICIPALITY]->(c)
  `);

  console.log("Relationships created");
}

async function main() {
  const clearFlag = Deno.args.includes("--clear");

  try {
    console.log("Loading PSGC data from psa/psgc_data.jsonl...");
    const data = await readJSONLFile("psa/psgc_data.jsonl");
    console.log(`Loaded ${data.length} records`);

    if (clearFlag) {
      await clearDatabase();
    }

    await createIndexes();

    const regions = data.filter((d) =>
      d.is_region && d.province_code === "000"
    );
    const provinces = data.filter((d) =>
      d.is_province && d.province_code !== "000" && d.municipality_code === "00"
    );
    const cities = data.filter((d) =>
      d.is_city_municipality ||
      (d.municipality_code !== "00" && d.barangay_code === "000" &&
        !d.is_submunicipality)
    );
    const barangays = data.filter((d) => d.is_barangay);
    const submuns = data.filter((d) => d.geographic_level === "SubMun");

    console.log(`Found ${regions.length} regions`);
    console.log(`Found ${provinces.length} provinces`);
    console.log(`Found ${cities.length} cities/municipalities`);
    console.log(`Found ${barangays.length} barangays`);
    console.log(`Found ${submuns.length} sub-municipalities`);

    const regionProps = [
      "psgc_code",
      "name",
      "correspondence_code",
      "geographic_level",
      "population_2020",
      "region_code",
      "province_code",
      "municipality_code",
      "barangay_code",
    ];
    const provinceProps = [
      "psgc_code",
      "name",
      "correspondence_code",
      "geographic_level",
      "population_2020",
      "region_code",
      "province_code",
      "municipality_code",
      "barangay_code",
    ];
    // Add a 'type' field to distinguish cities from municipalities
    const cityProps = [
      "psgc_code",
      "name",
      "correspondence_code",
      "geographic_level",
      "city_class",
      "income_classification",
      "population_2020",
      "region_code",
      "province_code",
      "municipality_code",
      "barangay_code",
      "type",
    ];
    const barangayProps = [
      "psgc_code",
      "name",
      "correspondence_code",
      "geographic_level",
      "urban_rural",
      "population_2020",
      "region_code",
      "province_code",
      "municipality_code",
      "barangay_code",
    ];

    console.log("\nImporting regions...");
    for (let i = 0; i < regions.length; i += BATCH_SIZE) {
      const batch = regions.slice(i, i + BATCH_SIZE);
      await importBatch(batch, "Region", regionProps);
      console.log(
        `  Imported ${
          Math.min(i + BATCH_SIZE, regions.length)
        }/${regions.length} regions`,
      );
    }

    console.log("\nImporting provinces...");
    for (let i = 0; i < provinces.length; i += BATCH_SIZE) {
      const batch = provinces.slice(i, i + BATCH_SIZE);
      await importBatch(batch, "Province", provinceProps);
      console.log(
        `  Imported ${
          Math.min(i + BATCH_SIZE, provinces.length)
        }/${provinces.length} provinces`,
      );
    }

    console.log("\nImporting cities/municipalities...");
    // Add 'type' field to distinguish cities from municipalities
    const citiesWithType = cities.map((c) => ({
      ...c,
      type: c.geographic_level === "City" ? "city" : "municipality",
    }));

    for (let i = 0; i < citiesWithType.length; i += BATCH_SIZE) {
      const batch = citiesWithType.slice(i, i + BATCH_SIZE);
      await importBatch(batch, "CityMunicipality", cityProps);
      console.log(
        `  Imported ${
          Math.min(i + BATCH_SIZE, citiesWithType.length)
        }/${citiesWithType.length} cities/municipalities`,
      );
    }

    console.log("\nImporting barangays...");
    for (let i = 0; i < barangays.length; i += BATCH_SIZE) {
      const batch = barangays.slice(i, i + BATCH_SIZE);
      await importBatch(batch, "Barangay", barangayProps);
      console.log(
        `  Imported ${
          Math.min(i + BATCH_SIZE, barangays.length)
        }/${barangays.length} barangays`,
      );
    }

    console.log("\nImporting sub-municipalities...");
    for (let i = 0; i < submuns.length; i += BATCH_SIZE) {
      const batch = submuns.slice(i, i + BATCH_SIZE);
      await importBatch(batch, "SubMunicipality", barangayProps);
      console.log(
        `  Imported ${
          Math.min(i + BATCH_SIZE, submuns.length)
        }/${submuns.length} sub-municipalities`,
      );
    }

    console.log("\nCreating relationships...");
    await createRelationships();

    console.log("\n✅ Import completed successfully!");

    console.log("\nVerifying import...");
    const stats = await runQuery(`
      MATCH (r:Region) WITH count(r) as regions
      MATCH (p:Province) WITH regions, count(p) as provinces
      MATCH (c:CityMunicipality) 
      WITH regions, provinces, 
           count(c) as total_cities_municipalities,
           count(CASE WHEN c.type = 'city' THEN 1 END) as cities,
           count(CASE WHEN c.type = 'municipality' THEN 1 END) as municipalities
      MATCH (b:Barangay) 
      RETURN regions, provinces, cities, municipalities, total_cities_municipalities, count(b) as barangays
    `);

    if (stats && stats[0]) {
      console.log("\nDatabase statistics:");
      console.log("  Regions:", stats[0].regions);
      console.log("  Provinces:", stats[0].provinces);
      console.log("  Cities:", stats[0].cities);
      console.log("  Municipalities:", stats[0].municipalities);
      console.log(
        "  Total Cities/Municipalities:",
        stats[0].total_cities_municipalities,
      );
      console.log("  Barangays:", stats[0].barangays);
    }
  } catch (error) {
    console.error("Import failed:", error);
    Deno.exit(1);
  } finally {
    await closeDriver();
  }
}

if (import.meta.main) {
  await main();
}
