import neo4j, { Driver, Session } from "neo4j";

export { neo4j };

let driver: Driver | null = null;

export function getDriver(): Driver {
  if (!driver) {
    const uri = Deno.env.get("NEO4J_URI");
    const username = Deno.env.get("NEO4J_USERNAME");
    const password = Deno.env.get("NEO4J_PASSWORD") ||
      Deno.env.get("NEO4J_PASSWORD");

    if (!uri || !username || !password) {
      throw new Error("Missing Neo4j connection environment variables");
    }

    driver = neo4j.driver(
      uri,
      neo4j.auth.basic(username, password),
      { maxConnectionLifetime: 3600000 },
    );
  }
  return driver;
}

export async function closeDriver(): Promise<void> {
  if (driver) {
    await driver.close();
    driver = null;
  }
}

export function getSession(): Session {
  return getDriver().session();
}

export async function runQuery<T = any>(
  cypher: string,
  params?: Record<string, any>,
): Promise<T[]> {
  const session = getSession();
  try {
    const result = await session.run(cypher, params);
    return result.records.map((record) => {
      const obj: any = {};
      record.keys.forEach((key) => {
        const value = record.get(key);
        obj[key] = value?.properties || value;
      });
      return obj;
    });
  } finally {
    await session.close();
  }
}

export async function runWrite(
  cypher: string,
  params?: Record<string, any>,
): Promise<void> {
  const session = getSession();
  try {
    await session.run(cypher, params);
  } finally {
    await session.close();
  }
}

export async function clearDatabase(): Promise<void> {
  console.log("Clearing database...");
  await runWrite("MATCH (n) DETACH DELETE n");
  console.log("Database cleared");
}

export async function createIndexes(): Promise<void> {
  console.log("Creating indexes...");
  const indexes = [
    "CREATE INDEX region_psgc IF NOT EXISTS FOR (r:Region) ON (r.psgc_code)",
    "CREATE INDEX province_psgc IF NOT EXISTS FOR (p:Province) ON (p.psgc_code)",
    "CREATE INDEX city_municipality_psgc IF NOT EXISTS FOR (c:CityMunicipality) ON (c.psgc_code)",
    "CREATE INDEX barangay_psgc IF NOT EXISTS FOR (b:Barangay) ON (b.psgc_code)",
    "CREATE INDEX submunicipality_psgc IF NOT EXISTS FOR (s:SubMunicipality) ON (s.psgc_code)",
    "CREATE INDEX region_name IF NOT EXISTS FOR (r:Region) ON (r.name)",
    "CREATE INDEX province_name IF NOT EXISTS FOR (p:Province) ON (p.name)",
    "CREATE INDEX city_municipality_name IF NOT EXISTS FOR (c:CityMunicipality) ON (c.name)",
    "CREATE INDEX barangay_name IF NOT EXISTS FOR (b:Barangay) ON (b.name)",
  ];

  for (const index of indexes) {
    try {
      await runWrite(index);
    } catch (error) {
      console.warn(`Index might already exist: ${error}`);
    }
  }
  console.log("Indexes created");
}
