import { Handlers } from "$fresh/server.ts";
import { runQuery } from "../../../src/neo4j.ts";

export const handler: Handlers = {
  async GET(_req, ctx) {
    const { psgc_code } = ctx.params;
    try {
      // Query any node with the given PSGC code
      const nodeData = await runQuery(
        `
        MATCH (n {psgc_code: $psgc_code})
        OPTIONAL MATCH (parent)-[r]->(n)
        OPTIONAL MATCH (n)-[r2]->(child)
        WITH n, 
             labels(n) as nodeLabels,
             collect(DISTINCT {
               relationship: type(r),
               parent: parent,
               parentLabels: labels(parent)
             }) as parents,
             collect(DISTINCT {
               relationship: type(r2),
               child: child,
               childLabels: labels(child)
             }) as children
        RETURN n as node,
               nodeLabels[0] as type,
               parents,
               children
      `,
        { psgc_code },
      );

      if (!nodeData || nodeData.length === 0) {
        return Response.json(
          { error: "Node not found" },
          { status: 404 },
        );
      }

      const result = nodeData[0];

      // Clean up the parents and children arrays
      const cleanParents = result.parents
        .filter((p: any) => p.parent)
        .map((p: any) => ({
          relationship: p.relationship,
          node: p.parent,
          type: p.parentLabels?.[0] || "Unknown",
        }));

      const cleanChildren = result.children
        .filter((c: any) => c.child)
        .map((c: any) => ({
          relationship: c.relationship,
          node: c.child,
          type: c.childLabels?.[0] || "Unknown",
        }));

      // Get hierarchical path
      const hierarchy = await runQuery(
        `
        MATCH (target {psgc_code: $psgc_code})
        OPTIONAL MATCH (r:Region)
        WHERE EXISTS((r)-[*0..4]->(target)) OR r = target
        WITH target, r
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
        RETURN collect(DISTINCT {
          type: labels(node)[0],
          psgc_code: node.psgc_code,
          name: node.name
        }) as path
      `,
        { psgc_code },
      );

      return Response.json({
        node: result.node,
        type: result.type,
        parents: cleanParents,
        children: cleanChildren,
        hierarchy: hierarchy[0]?.path || [],
        relationships: {
          parentCount: cleanParents.length,
          childCount: cleanChildren.length,
        },
      });
    } catch (error) {
      console.error("Error fetching node details:", error);
      return Response.json(
        {
          error: "Failed to fetch node details",
          details: error instanceof Error ? error.message : String(error),
        },
        { status: 500 },
      );
    }
  },
};
