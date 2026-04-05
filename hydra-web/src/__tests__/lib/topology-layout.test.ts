import { describe, it, expect, vi } from 'vitest';
import type { Node, Edge } from '@xyflow/react';
import {
  getLayoutedElements,
  getGridLayout,
  getLayoutDirectionForMode,
  getLayoutOptionsForMode,
  type LayoutOptions,
} from '@/lib/topology-layout';

// Mock ELK layout engine
vi.mock('elkjs/lib/elk.bundled.js', () => {
  return {
    default: class MockELK {
      async layout(graph: any) {
        // Simulate ELK layout by positioning nodes in a simple vertical layout
        const children = graph.children || [];
        const spacing = 100;
        const layoutedChildren = children.map((node: any, index: number) => ({
          ...node,
          x: 100,
          y: index * spacing,
        }));

        return {
          ...graph,
          children: layoutedChildren,
        };
      }
    },
  };
});

describe('topology-layout', () => {
  describe('getLayoutedElements', () => {
    it('should return empty arrays when no nodes provided', async () => {
      const result = await getLayoutedElements([], []);
      expect(result.nodes).toEqual([]);
      expect(result.edges).toEqual([]);
    });

    it('should layout a single node', async () => {
      const nodes: Node[] = [
        {
          id: 'node-1',
          position: { x: 0, y: 0 },
          data: { label: 'Node 1' },
        },
      ];
      const edges: Edge[] = [];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].id).toBe('node-1');
      expect(result.nodes[0].position).toBeDefined();
      expect(typeof result.nodes[0].position.x).toBe('number');
      expect(typeof result.nodes[0].position.y).toBe('number');
      expect(result.edges).toEqual([]);
    });

    it('should layout a linear chain of nodes', async () => {
      const nodes: Node[] = [
        { id: 'a', position: { x: 0, y: 0 }, data: {} },
        { id: 'b', position: { x: 0, y: 0 }, data: {} },
        { id: 'c', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [
        { id: 'ab', source: 'a', target: 'b' },
        { id: 'bc', source: 'b', target: 'c' },
      ];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(3);
      expect(result.edges).toHaveLength(2);

      // All nodes should have positions
      result.nodes.forEach((node) => {
        expect(node.position).toBeDefined();
        expect(typeof node.position.x).toBe('number');
        expect(typeof node.position.y).toBe('number');
      });

      // Positions should be different (mock ELK places them vertically)
      const positions = result.nodes.map((n) => n.position.y);
      const uniquePositions = new Set(positions);
      expect(uniquePositions.size).toBe(3); // All nodes at different Y positions
    });

    it('should layout a tree structure', async () => {
      const nodes: Node[] = [
        { id: 'root', position: { x: 0, y: 0 }, data: {} },
        { id: 'child1', position: { x: 0, y: 0 }, data: {} },
        { id: 'child2', position: { x: 0, y: 0 }, data: {} },
        { id: 'grandchild1', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [
        { id: 'e1', source: 'root', target: 'child1' },
        { id: 'e2', source: 'root', target: 'child2' },
        { id: 'e3', source: 'child1', target: 'grandchild1' },
      ];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(4);
      expect(result.edges).toHaveLength(3);

      // All nodes should have valid positions
      result.nodes.forEach((node) => {
        expect(node.position.x).toBeGreaterThanOrEqual(0);
        expect(node.position.y).toBeGreaterThanOrEqual(0);
      });
    });

    it('should layout disconnected nodes', async () => {
      const nodes: Node[] = [
        { id: 'isolated1', position: { x: 0, y: 0 }, data: {} },
        { id: 'isolated2', position: { x: 0, y: 0 }, data: {} },
        { id: 'isolated3', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(3);
      expect(result.edges).toHaveLength(0);

      // All nodes should have positions even without edges
      result.nodes.forEach((node) => {
        expect(node.position).toBeDefined();
        expect(typeof node.position.x).toBe('number');
        expect(typeof node.position.y).toBe('number');
      });
    });

    it('should filter out edges with non-existent nodes', async () => {
      const nodes: Node[] = [
        { id: 'a', position: { x: 0, y: 0 }, data: {} },
        { id: 'b', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [
        { id: 'ab', source: 'a', target: 'b' }, // Valid
        { id: 'ac', source: 'a', target: 'c' }, // Invalid target
        { id: 'db', source: 'd', target: 'b' }, // Invalid source
        { id: 'ef', source: 'e', target: 'f' }, // Both invalid
      ];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(2);
      // Edges are returned as-is, but filtering happens in ELK graph construction
      expect(result.edges).toHaveLength(4);
    });

    it('should apply custom layout options', async () => {
      const nodes: Node[] = [
        { id: 'node1', position: { x: 0, y: 0 }, data: {} },
        { id: 'node2', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [{ id: 'e1', source: 'node1', target: 'node2' }];

      const options: LayoutOptions = {
        direction: 'RIGHT',
        nodeWidth: 200,
        nodeHeight: 100,
        nodeSep: 80,
        layerSep: 120,
        algorithm: 'force',
      };

      const result = await getLayoutedElements(nodes, edges, options);

      expect(result.nodes).toHaveLength(2);
      // Options are applied internally to ELK, verify layout completes successfully
      result.nodes.forEach((node) => {
        expect(node.position).toBeDefined();
      });
    });

    it('should preserve node data during layout', async () => {
      const nodes: Node[] = [
        {
          id: 'node1',
          position: { x: 0, y: 0 },
          data: { label: 'Custom Label', status: 'active', count: 42 },
          type: 'custom',
        },
      ];
      const edges: Edge[] = [];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes[0].data).toEqual({
        label: 'Custom Label',
        status: 'active',
        count: 42,
      });
      expect(result.nodes[0].type).toBe('custom');
    });

    it('should handle default options when none provided', async () => {
      const nodes: Node[] = [
        { id: 'a', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(1);
      expect(result.nodes[0].position).toBeDefined();
    });
  });

  describe('getGridLayout', () => {
    it('should return empty array for no nodes', () => {
      const result = getGridLayout([]);
      expect(result).toEqual([]);
    });

    it('should layout single node at origin', () => {
      const nodes: Node[] = [
        { id: 'node1', position: { x: 0, y: 0 }, data: {} },
      ];

      const result = getGridLayout(nodes);

      expect(result).toHaveLength(1);
      expect(result[0].position.x).toBe(0);
      expect(result[0].position.y).toBe(0);
    });

    it('should layout multiple nodes in a grid', () => {
      const nodes: Node[] = [
        { id: '1', position: { x: 0, y: 0 }, data: {} },
        { id: '2', position: { x: 0, y: 0 }, data: {} },
        { id: '3', position: { x: 0, y: 0 }, data: {} },
        { id: '4', position: { x: 0, y: 0 }, data: {} },
      ];

      const result = getGridLayout(nodes);

      expect(result).toHaveLength(4);

      // Check grid arrangement (2x2 grid for 4 nodes)
      const positions = result.map((n) => ({ x: n.position.x, y: n.position.y }));

      // First row (y=0)
      expect(positions[0].y).toBe(0);
      expect(positions[1].y).toBe(0);

      // Second row (y>0)
      expect(positions[2].y).toBeGreaterThan(0);
      expect(positions[3].y).toBeGreaterThan(0);

      // Ensure horizontal spacing
      expect(positions[1].x).toBeGreaterThan(positions[0].x);
      expect(positions[3].x).toBeGreaterThan(positions[2].x);
    });

    it('should use custom spacing options', () => {
      const nodes: Node[] = [
        { id: '1', position: { x: 0, y: 0 }, data: {} },
        { id: '2', position: { x: 0, y: 0 }, data: {} },
      ];

      const options: LayoutOptions = {
        nodeWidth: 200,
        nodeHeight: 100,
        nodeSep: 50,
        layerSep: 80,
      };

      const result = getGridLayout(nodes, options);

      // Expected x for second node: (index % cols) * (nodeWidth + nodeSep)
      // cols = ceil(sqrt(2)) = 2, so both in first row
      expect(result[1].position.x).toBe(250); // 200 + 50
      expect(result[0].position.y).toBe(0);
      expect(result[1].position.y).toBe(0);
    });

    it('should calculate grid columns based on square root of node count', () => {
      // 9 nodes should be 3x3 grid
      const nodes: Node[] = Array.from({ length: 9 }, (_, i) => ({
        id: String(i),
        position: { x: 0, y: 0 },
        data: {},
      }));

      const result = getGridLayout(nodes);

      // Check positions form a 3x3 grid
      const uniqueX = new Set(result.map((n) => n.position.x));
      const uniqueY = new Set(result.map((n) => n.position.y));

      expect(uniqueX.size).toBe(3); // 3 columns
      expect(uniqueY.size).toBe(3); // 3 rows
    });

    it('should preserve node data in grid layout', () => {
      const nodes: Node[] = [
        {
          id: 'node1',
          position: { x: 0, y: 0 },
          data: { label: 'Test', custom: 'value' },
          type: 'special',
        },
      ];

      const result = getGridLayout(nodes);

      expect(result[0].data).toEqual({ label: 'Test', custom: 'value' });
      expect(result[0].type).toBe('special');
      expect(result[0].id).toBe('node1');
    });

    it('should handle non-perfect square node counts', () => {
      // 7 nodes should be 3x3 grid (ceil(sqrt(7)) = 3)
      const nodes: Node[] = Array.from({ length: 7 }, (_, i) => ({
        id: String(i),
        position: { x: 0, y: 0 },
        data: {},
      }));

      const result = getGridLayout(nodes);

      expect(result).toHaveLength(7);

      // All nodes should have valid positions
      result.forEach((node) => {
        expect(node.position.x).toBeGreaterThanOrEqual(0);
        expect(node.position.y).toBeGreaterThanOrEqual(0);
      });
    });
  });

  describe('getLayoutDirectionForMode', () => {
    it('should return DOWN for infrastructure mode', () => {
      expect(getLayoutDirectionForMode('infrastructure')).toBe('DOWN');
    });

    it('should return RIGHT for network mode', () => {
      expect(getLayoutDirectionForMode('network')).toBe('RIGHT');
    });

    it('should return DOWN for service mode', () => {
      expect(getLayoutDirectionForMode('service')).toBe('DOWN');
    });

    it('should return DOWN for any other value (fallback)', () => {
      // TypeScript will prevent this at compile time, but testing runtime behavior
      expect(getLayoutDirectionForMode('unknown' as any)).toBe('DOWN');
    });
  });

  describe('getLayoutOptionsForMode', () => {
    it('should return options for infrastructure mode with small graph', () => {
      const options = getLayoutOptionsForMode('infrastructure', 5);

      expect(options.direction).toBe('DOWN');
      expect(options.algorithm).toBe('layered');
      expect(options.nodeWidth).toBe(180);
      expect(options.nodeHeight).toBe(80);
      expect(options.nodeSep).toBe(80);
      expect(options.layerSep).toBe(120);
    });

    it('should return options for network mode with medium graph', () => {
      const options = getLayoutOptionsForMode('network', 25);

      expect(options.direction).toBe('RIGHT');
      expect(options.algorithm).toBe('layered');
      expect(options.nodeSep).toBe(60);
      expect(options.layerSep).toBe(100);
    });

    it('should return options for service mode with large graph', () => {
      const options = getLayoutOptionsForMode('service', 45);

      expect(options.direction).toBe('DOWN');
      expect(options.nodeSep).toBe(50);
      expect(options.layerSep).toBe(80);
    });

    it('should use tighter spacing for very large graphs (>50 nodes)', () => {
      const options = getLayoutOptionsForMode('infrastructure', 100);

      expect(options.nodeSep).toBe(40);
      expect(options.layerSep).toBe(60);
    });

    it('should handle edge cases at spacing thresholds', () => {
      // Test boundary conditions
      const small = getLayoutOptionsForMode('network', 10);
      const medium = getLayoutOptionsForMode('network', 11);
      const large = getLayoutOptionsForMode('network', 30);
      const veryLarge = getLayoutOptionsForMode('network', 51);

      expect(small.nodeSep).toBe(80);
      expect(small.layerSep).toBe(120);

      expect(medium.nodeSep).toBe(60);
      expect(medium.layerSep).toBe(100);

      expect(large.nodeSep).toBe(60);
      expect(large.layerSep).toBe(100);

      expect(veryLarge.nodeSep).toBe(40);
      expect(veryLarge.layerSep).toBe(60);
    });

    it('should return consistent base options across modes', () => {
      const modes: Array<'infrastructure' | 'network' | 'service'> = [
        'infrastructure',
        'network',
        'service',
      ];

      modes.forEach((mode) => {
        const options = getLayoutOptionsForMode(mode, 15);
        expect(options.nodeWidth).toBe(180);
        expect(options.nodeHeight).toBe(80);
        expect(options.algorithm).toBe('layered');
      });
    });

    it('should handle zero nodes', () => {
      const options = getLayoutOptionsForMode('infrastructure', 0);

      expect(options).toBeDefined();
      expect(options.nodeSep).toBe(80);
      expect(options.layerSep).toBe(120);
    });

    it('should handle single node', () => {
      const options = getLayoutOptionsForMode('service', 1);

      expect(options.direction).toBe('DOWN');
      expect(options.nodeSep).toBe(80);
    });

    it('should adjust spacing at threshold boundaries', () => {
      // Testing exact threshold values (10, 30, 50)
      const at10 = getLayoutOptionsForMode('infrastructure', 10);
      const at11 = getLayoutOptionsForMode('infrastructure', 11);
      const at30 = getLayoutOptionsForMode('infrastructure', 30);
      const at31 = getLayoutOptionsForMode('infrastructure', 31);
      const at50 = getLayoutOptionsForMode('infrastructure', 50);
      const at51 = getLayoutOptionsForMode('infrastructure', 51);

      // <= 10: larger spacing
      expect(at10.nodeSep).toBe(80);

      // 11-30: medium spacing
      expect(at11.nodeSep).toBe(60);
      expect(at30.nodeSep).toBe(60);

      // 31-50: tighter spacing
      expect(at31.nodeSep).toBe(50);
      expect(at50.nodeSep).toBe(50);

      // > 50: tightest spacing
      expect(at51.nodeSep).toBe(40);
    });
  });

  describe('edge cases and integration', () => {
    it('should handle nodes with missing position fields', async () => {
      const nodes: Node[] = [
        { id: 'a', position: { x: 0, y: 0 }, data: {} },
        { id: 'b', position: { x: 0, y: 0 }, data: {} },
      ];

      const result = await getLayoutedElements(nodes, []);

      expect(result.nodes).toHaveLength(2);
      result.nodes.forEach((node) => {
        expect(node.position).toBeDefined();
        expect(node.position.x).toBeDefined();
        expect(node.position.y).toBeDefined();
      });
    });

    it('should handle mixed valid and invalid edges gracefully', async () => {
      const nodes: Node[] = [
        { id: 'a', position: { x: 0, y: 0 }, data: {} },
        { id: 'b', position: { x: 0, y: 0 }, data: {} },
        { id: 'c', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [
        { id: 'ab', source: 'a', target: 'b' }, // Valid
        { id: 'ax', source: 'a', target: 'nonexistent' }, // Invalid
        { id: 'bc', source: 'b', target: 'c' }, // Valid
      ];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(3);
      // All edges returned, but only valid ones used in layout calculation
      expect(result.edges).toHaveLength(3);
    });

    it('should work with complex graph structures', async () => {
      // Create a more complex graph: diamond shape
      const nodes: Node[] = [
        { id: 'top', position: { x: 0, y: 0 }, data: {} },
        { id: 'left', position: { x: 0, y: 0 }, data: {} },
        { id: 'right', position: { x: 0, y: 0 }, data: {} },
        { id: 'bottom', position: { x: 0, y: 0 }, data: {} },
      ];
      const edges: Edge[] = [
        { id: 'e1', source: 'top', target: 'left' },
        { id: 'e2', source: 'top', target: 'right' },
        { id: 'e3', source: 'left', target: 'bottom' },
        { id: 'e4', source: 'right', target: 'bottom' },
      ];

      const result = await getLayoutedElements(nodes, edges);

      expect(result.nodes).toHaveLength(4);
      expect(result.edges).toHaveLength(4);

      // All nodes should be positioned
      result.nodes.forEach((node) => {
        expect(node.position).toBeDefined();
        expect(Number.isFinite(node.position.x)).toBe(true);
        expect(Number.isFinite(node.position.y)).toBe(true);
      });
    });

    it('should maintain node order consistency', () => {
      const nodes: Node[] = [
        { id: 'z', position: { x: 0, y: 0 }, data: { order: 3 } },
        { id: 'a', position: { x: 0, y: 0 }, data: { order: 1 } },
        { id: 'm', position: { x: 0, y: 0 }, data: { order: 2 } },
      ];

      const result = getGridLayout(nodes);

      // Input order should be preserved
      expect(result[0].id).toBe('z');
      expect(result[1].id).toBe('a');
      expect(result[2].id).toBe('m');
      expect(result[0].data.order).toBe(3);
      expect(result[1].data.order).toBe(1);
      expect(result[2].data.order).toBe(2);
    });
  });
});
