import { Head } from "$fresh/runtime.ts";
import { Handlers, PageProps } from "$fresh/server.ts";
import { runQuery } from "../src/neo4j.ts";

interface StatsData {
  regions: number;
  provinces: number;
  cities: number;
  municipalities: number;
  barangays: number;
  examples: {
    region?: string;
    province?: string;
    city?: string;
    barangay?: string;
  };
}

export const handler: Handlers<StatsData> = {
  async GET(_req, ctx) {
    let stats = { regions: 0, provinces: 0, cities: 0, municipalities: 0, barangays: 0 };
    let examples = {};
    
    try {
      // Get counts
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
        stats = {
          regions: Number(counts[0].regions) || 0,
          provinces: Number(counts[0].provinces) || 0,
          cities: Number(counts[0].cities) || 0,
          municipalities: Number(counts[0].municipalities) || 0,
          barangays: Number(counts[0].barangays) || 0
        };
      }

      // Get example PSGC codes for "Try it" buttons
      const exampleData = await runQuery(`
        MATCH (r:Region) 
        WITH r ORDER BY r.psgc_code LIMIT 1
        MATCH (p:Province) 
        WITH r, p ORDER BY p.psgc_code LIMIT 1
        MATCH (c:CityMunicipality {type: 'city'}) 
        WITH r, p, c ORDER BY c.psgc_code LIMIT 1
        MATCH (b:Barangay)
        WITH r, p, c, b ORDER BY b.psgc_code LIMIT 1
        RETURN r.psgc_code as region, 
               p.psgc_code as province, 
               c.psgc_code as city, 
               b.psgc_code as barangay
      `);
      if (exampleData && exampleData[0]) {
        examples = exampleData[0];
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    }
    
    return ctx.render({ ...stats, examples });
  },
};

export default function Home({ data, url }: PageProps<StatsData>) {
  const origin = url.origin;
  
  return (
    <>
      <Head>
        <title>Philippine Datasets API</title>
        <link rel="stylesheet" href="/styles.css" />
      </Head>
      
      <div class="min-h-screen bg-gradient-to-br from-purple-600 to-purple-800 p-5">
        <div class="max-w-7xl mx-auto bg-white rounded-3xl shadow-2xl overflow-hidden">
          <header class="bg-gradient-to-r from-red-600 to-orange-600 text-white py-12 px-8 text-center">
            <h1 class="text-4xl font-bold mb-4">🇵🇭 Philippine Datasets API</h1>
            <p class="text-xl opacity-95">Open data from Philippine government agencies, mapped and connected with Neo4j</p>
          </header>

          <div class="grid grid-cols-2 md:grid-cols-5 gap-4 p-8 bg-gray-50 border-b">
            <div class="bg-white p-6 rounded-xl text-center shadow-md">
              <div class="text-3xl font-bold text-purple-600">{data.regions.toLocaleString('en-US')}</div>
              <div class="text-gray-600 mt-2">Regions</div>
            </div>
            <div class="bg-white p-6 rounded-xl text-center shadow-md">
              <div class="text-3xl font-bold text-purple-600">{data.provinces.toLocaleString('en-US')}</div>
              <div class="text-gray-600 mt-2">Provinces</div>
            </div>
            <div class="bg-white p-6 rounded-xl text-center shadow-md">
              <div class="text-3xl font-bold text-purple-600">{data.cities.toLocaleString('en-US')}</div>
              <div class="text-gray-600 mt-2">Cities</div>
            </div>
            <div class="bg-white p-6 rounded-xl text-center shadow-md">
              <div class="text-3xl font-bold text-purple-600">{data.municipalities.toLocaleString('en-US')}</div>
              <div class="text-gray-600 mt-2">Municipalities</div>
            </div>
            <div class="bg-white p-6 rounded-xl text-center shadow-md">
              <div class="text-3xl font-bold text-purple-600">{data.barangays.toLocaleString('en-US')}</div>
              <div class="text-gray-600 mt-2">Barangays</div>
            </div>
          </div>

          <div class="p-8 space-y-8">
            <section>
              <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">📋 List Endpoints</h2>
              <div class="grid gap-3">
                <ApiEndpoint method="GET" path="/api/regions" description="List all regions in the Philippines" />
                <ApiEndpoint method="GET" path="/api/provinces" description="List all provinces with their parent region" />
                <ApiEndpoint method="GET" path="/api/cities" description="List all cities (HUC, ICC, CC) with province and region" />
                <ApiEndpoint method="GET" path="/api/municipalities" description="List all municipalities with province and region" />
                <ApiEndpoint method="GET" path="/api/localities" description="List all cities and municipalities combined with type field" />
                <ApiEndpoint method="GET" path="/api/barangays?limit=100&offset=0&sort=name" description="List barangays (paginated and sortable by psgc_code, name, or population)" />
              </div>
            </section>

            <section>
              <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">🔍 Detail Endpoints</h2>
              <div class="grid gap-3">
                <ApiEndpoint 
                  method="GET" 
                  path="/api/regions/:psgc_code" 
                  description="Get specific region with all its provinces" 
                  tryUrl={data.examples.region ? `/api/regions/${data.examples.region}` : undefined}
                />
                <ApiEndpoint 
                  method="GET" 
                  path="/api/provinces/:psgc_code" 
                  description="Get specific province with all its cities/municipalities" 
                  tryUrl={data.examples.province ? `/api/provinces/${data.examples.province}` : undefined}
                />
                <ApiEndpoint 
                  method="GET" 
                  path="/api/cities/:psgc_code" 
                  description="Get specific city/municipality with all its barangays" 
                  tryUrl={data.examples.city ? `/api/cities/${data.examples.city}` : undefined}
                />
                <ApiEndpoint 
                  method="GET" 
                  path="/api/barangays/:psgc_code" 
                  description="Get specific barangay with complete hierarchy" 
                  tryUrl={data.examples.barangay ? `/api/barangays/${data.examples.barangay}` : undefined}
                />
              </div>
            </section>

            <section>
              <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">🛠️ Utility Endpoints</h2>
              <div class="grid gap-3">
                <ApiEndpoint 
                  method="GET" 
                  path="/api/detail/:psgc_code" 
                  description="Get any node by PSGC code with its relationships and hierarchy" 
                  tryUrl={data.examples.city ? `/api/detail/${data.examples.city}` : undefined}
                />
                <ApiEndpoint 
                  method="GET" 
                  path="/api/search?q=:query&limit=:limit&offset=:offset&sort=:sort&type=:type" 
                  description="Search locations by name (paginated, sortable, filterable)" 
                  tryUrl="/api/search?q=manila&limit=10&offset=0&sort=name&type=city"
                />
                <ApiEndpoint 
                  method="GET" 
                  path="/api/hierarchy/:psgc_code" 
                  description="Get complete hierarchical path from region to target location" 
                  tryUrl={data.examples.barangay ? `/api/hierarchy/${data.examples.barangay}` : undefined}
                />
              </div>
            </section>

            <section>
              <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">💡 Example Usage</h2>
              <div class="bg-gray-900 p-4 rounded-lg overflow-x-auto">
                <CodeExample origin={origin} />
              </div>
            </section>

            <section>
              <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">🔍 Search Parameters</h2>
              <div class="bg-gray-50 p-4 rounded-lg">
                <dl class="space-y-3">
                  <SearchParam name="q" required={true} description="Search query string to match against location names" />
                  <SearchParam name="limit" description="Number of results per page (default: 100)" />
                  <SearchParam name="offset" description="Number of results to skip for pagination (default: 0)" />
                  <SearchParam name="sort" description="Sort results by: psgc_code, name (default), or population (descending)" />
                  <SearchParam name="type" description="Filter by location type: region, province, city, municipality, or barangay" />
                </dl>
              </div>
            </section>

            <GlossarySection />
          </div>

          <footer class="bg-gray-50 p-8 text-center text-gray-600">
            <p>Data Source: <a href="https://psa.gov.ph/" target="_blank" class="text-purple-600 hover:underline">Philippine Statistics Authority</a></p>
            <p class="mt-2">
              Built with ❤️ using{" "}
              <a href="https://deno.com/" target="_blank" class="text-purple-600 hover:underline">Deno</a>,{" "}
              <a href="https://fresh.deno.dev/" target="_blank" class="text-purple-600 hover:underline">Fresh</a>, and{" "}
              <a href="https://neo4j.com/" target="_blank" class="text-purple-600 hover:underline">Neo4j</a>
            </p>
            <p class="mt-2"><a href="https://github.com/wewillcraft/philippines-datasets" target="_blank" class="text-purple-600 hover:underline">View on GitHub</a></p>
          </footer>
        </div>
      </div>
    </>
  );
}

function ApiEndpoint({ method, path, description, tryUrl }: { method: string; path: string; description: string; tryUrl?: string }) {
  return (
    <div class="bg-gray-50 p-4 rounded-lg border-l-4 border-purple-600 hover:bg-gray-100 hover:translate-x-1 transition-all font-mono relative">
      <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div class="flex-1 min-w-0">
          <div class="flex items-center flex-wrap">
            <span class="inline-block bg-green-500 text-white px-2 py-1 rounded text-xs font-bold mr-2">{method}</span>
            <span class="font-bold text-gray-700 break-all">{path}</span>
          </div>
          <div class="text-gray-600 text-sm mt-2 font-sans">{description}</div>
        </div>
        <a 
          href={tryUrl || path} 
          target="_blank" 
          class="inline-flex items-center justify-center px-4 py-2 sm:px-3 sm:py-1 bg-purple-600 hover:bg-purple-700 text-white text-xs font-semibold rounded transition-colors whitespace-nowrap w-full sm:w-auto"
        >
          Try it →
        </a>
      </div>
    </div>
  );
}

function CodeExample({ origin }: { origin: string }) {
  const examples = [
    { comment: "# Get all regions", command: "curl", url: `${origin}/api/regions` },
    { comment: "# Get any node by PSGC code (works for region, province, city, or barangay)", command: "curl", url: `${origin}/api/detail/1374000000` },
    { comment: "# Get details for NCR (National Capital Region)", command: "curl", url: `${origin}/api/regions/1300000000` },
    { comment: "# Search for locations containing \"Davao\"", command: "curl", url: `${origin}/api/search?q=davao&limit=10` },
    { comment: "# Search only cities containing \"Manila\", sorted by population", command: "curl", url: `${origin}/api/search?q=Manila&type=city&sort=population&limit=10` },
    { comment: "# Get complete hierarchy for Barangay Commonwealth, Quezon City", command: "curl", url: `${origin}/api/hierarchy/1374024000` },
    { comment: "# Get paginated barangays (page 2, 100 items per page)", command: "curl", url: `${origin}/api/barangays?limit=100&offset=100` },
  ];

  return (
    <pre class="text-sm overflow-x-auto">
      {examples.map((ex, idx) => (
        <div key={idx} class="mb-3 last:mb-0">
          <div class="text-gray-500 italic">{ex.comment}</div>
          <div>
            <span class="text-green-400">{ex.command}</span>{" "}
            <span class="text-blue-400">{ex.url}</span>
          </div>
        </div>
      ))}
    </pre>
  );
}

function SearchParam({ name, required = false, description }: { name: string; required?: boolean; description: string }) {
  return (
    <>
      <dt class="font-bold text-purple-600">
        {name} {required && <span class="text-red-500">*</span>}
      </dt>
      <dd class="ml-4 text-gray-600">{description}</dd>
    </>
  );
}

function GlossarySection() {
  return (
    <section>
      <h2 class="text-2xl font-bold text-gray-700 mb-4 pb-2 border-b-2 border-purple-600">📚 Glossary of Terms</h2>
      <div class="grid gap-4">
        <GlossaryCard title="Administrative Levels">
          <GlossaryTerm term="Region" definition="The highest administrative division in the Philippines, grouping provinces with geographical, cultural, and ethnological characteristics." />
          <GlossaryTerm term="Province" definition="The primary subdivision of regions, serving as the main unit for implementing national programs and policies." />
          <GlossaryTerm term="City" definition="A local government unit with its own charter passed by Congress. Cities have larger populations, higher income requirements (₱100M+ annually), and more autonomy than municipalities. They can be classified as Highly Urbanized (HUC), Independent Component (ICC), or Component Cities (CC) based on their relationship with provinces." />
          <GlossaryTerm term="Municipality" definition="The default local government unit created through provincial ordinances. Municipalities have smaller populations and lower income requirements (₱2.5M+ annually) compared to cities. They are always part of a province and residents vote for provincial officials. Most rural areas are organized as municipalities." />
          <GlossaryTerm term="Sub-Municipality" definition="A special administrative division within geographically large or archipelagic municipalities, particularly common in Palawan. Sub-municipalities have their own set of barangays but are not separate LGUs - they remain part of the parent municipality. They exist to improve service delivery in remote areas where the municipal center is difficult to reach. For example, Kalayaan municipality in Palawan has island sub-municipalities due to its scattered geography." />
          <GlossaryTerm term="Barangay" definition="The smallest administrative division in the Philippines and the basic unit of governance. Each barangay is headed by a Barangay Captain." />
        </GlossaryCard>

        <GlossaryCard title="City Classifications">
          <GlossaryTerm term="HUC - Highly Urbanized City" definition="Cities with a minimum population of 200,000 and annual income of ₱50 million. They are independent from provinces and have their own congressional districts." />
          <GlossaryTerm term="ICC - Independent Component City" definition="Component cities whose charters prohibit their residents from voting for provincial elective officials. They are independent from the province in certain aspects." />
          <GlossaryTerm term="CC - Component City" definition="Cities that are part of a province and whose residents can vote for provincial officials. They share tax revenues with the provincial government." />
        </GlossaryCard>

        <GlossaryCard title="Special Administrative Areas">
          <GlossaryTerm term="NCR - National Capital Region" definition="Also known as Metro Manila, it's the only region without provinces. Cities and municipalities report directly to the regional government." />
          <GlossaryTerm term="BARMM - Bangsamoro Autonomous Region" definition="An autonomous region with its own government system, created through the Bangsamoro Organic Law." />
          <GlossaryTerm term="CAR - Cordillera Administrative Region" definition="An administrative region created to administer the provinces with similar cultural and geographical characteristics in the Cordillera mountain range." />
        </GlossaryCard>

        <GlossaryCard title="PSGC Code Structure">
          <p class="text-gray-600 mb-2">The 10-digit PSGC code follows the format: <code class="bg-gray-800 text-gray-300 px-2 py-1 rounded">RR-PPP-LL-BBB</code></p>
          <ul class="ml-6 list-disc text-gray-600 space-y-1">
            <li><strong>RR</strong> - Region code (01-19)</li>
            <li><strong>PPP</strong> - Province code (000 for regions, 001-999 for provinces)</li>
            <li><strong>LL</strong> - Locality (Municipality/City) code (00 for provinces, 01-99 for cities/municipalities)</li>
            <li><strong>BBB</strong> - Barangay code (000 for cities/municipalities, 001-999 for barangays)</li>
          </ul>
          <p class="text-gray-600 mt-2">
            Example: <code class="bg-gray-800 text-gray-300 px-2 py-1 rounded">0301401007</code> represents Barangay 007 (Laog) in Locality 01 (Angat) of Province 014 (Bulacan) in Region 03 (Central Luzon).
          </p>
        </GlossaryCard>
      </div>
    </section>
  );
}

function GlossaryCard({ title, children }: { title: string; children: any }) {
  return (
    <div class="bg-gray-50 p-4 rounded-lg">
      <h3 class="text-lg font-semibold text-gray-700 mb-3">{title}</h3>
      <dl class="space-y-2">{children}</dl>
    </div>
  );
}

function GlossaryTerm({ term, definition }: { term: string; definition: string }) {
  return (
    <>
      <dt class="font-bold text-purple-600">{term}</dt>
      <dd class="ml-4 text-gray-600 mb-3">{definition}</dd>
    </>
  );
}