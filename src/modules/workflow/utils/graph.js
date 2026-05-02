/**
 * 获取节点的所有出边（从该节点发出的边）
 * @param {string} nodeId - 节点ID
 * @param {Array} edges - 边列表
 * @returns {Array} 出边数组
 */
export function getOutgoingEdges(nodeId, edges) {
  return edges.filter(edge => edge.source === nodeId)
}

/**
 * 获取节点的所有入边（指向该节点的边）
 * @param {string} nodeId - 节点ID
 * @param {Edge[]} edges - 边列表
 * @returns {Edge[]} 入边数组
 */
export function getIncomingEdges(nodeId, edges) {
  return edges.filter(edge => edge.target === nodeId)
}

/**
 * 获取节点的所有出节点（通过边连接的下一个节点）
 * @param {string} nodeId - 节点ID
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 出节点数组
 */
export function getOutgoingNodes(nodeId, nodes, edges) {
  const outgoingEdges = getOutgoingEdges(nodeId, edges)
  const targetIds = outgoingEdges.map(e => e.target)
  return nodes.filter(n => targetIds.includes(n.id))
}

/**
 * 获取节点的所有入节点（指向该节点的节点）
 * @param {string} nodeId - 节点ID
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 入节点数组
 */
export function getIncomingNodes(nodeId, nodes, edges) {
  const incomingEdges = getIncomingEdges(nodeId, edges)
  const sourceIds = incomingEdges.map(e => e.source)
  return nodes.filter(n => sourceIds.includes(n.id))
}

/**
 * 获取根节点（没有任何入边的节点）
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 根节点数组
 */
export function getRootNodes(nodes, edges) {
  const nodeIds = new Set(nodes.map(n => n.id))
  const hasIncoming = new Set(edges.map(e => e.target))
  return nodes.filter(n => !hasIncoming.has(n.id))
}

/**
 * 获取叶节点（没有任何出边的节点）
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 叶节点数组
 */
export function getLeafNodes(nodes, edges) {
  const nodeIds = new Set(nodes.map(n => n.id))
  const hasOutgoing = new Set(edges.map(e => e.source))
  return nodes.filter(n => !hasOutgoing.has(n.id))
}

/**
 * 检查两个节点是否直接相连
 * @param {string} sourceId - 源节点ID
 * @param {string} targetId - 目标节点ID
 * @param {Edge[]} edges - 边列表
 * @returns {boolean}
 */
export function isConnected(sourceId, targetId, edges) {
  return edges.some(e => e.source === sourceId && e.target === targetId)
}

/**
 * 获取节点层级（从根节点开始的距离）
 * @param {string} nodeId - 节点ID
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {number} 层级深度
 */
export function getNodeDepth(nodeId, nodes, edges) {
  const visited = new Set()
  let depth = 0
  const queue = [nodeId]

  while (queue.length > 0) {
    const levelSize = queue.length
    for (let i = 0; i < levelSize; i++) {
      const currentId = queue.shift()
      if (visited.has(currentId)) continue
      visited.add(currentId)

      const incoming = getIncomingNodes(currentId, nodes, edges)
      incoming.forEach(n => {
        if (!visited.has(n.id)) {
          queue.push(n.id)
        }
      })
    }
    if (queue.length > 0) depth++
  }

  return depth
}

/**
 * 获取从根到节点的路径
 * @param {string} nodeId - 节点ID
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 路径节点数组
 */
export function getPathToNode(nodeId, nodes, edges) {
  const path = []
  const visited = new Set()

  function traverse(currentId) {
    if (visited.has(currentId)) return
    visited.add(currentId)

    const node = nodes.find(n => n.id === currentId)
    if (node) path.push(node)

    const incoming = getIncomingNodes(currentId, nodes, edges)
    if (incoming.length > 0) {
      traverse(incoming[0].id)
    }
  }

  traverse(nodeId)
  return path.reverse()
}

/**
 * 拓扑排序
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {Node[]} 排序后的节点数组
 */
export function topologicalSort(nodes, edges) {
  const inDegree = {}
  const adjacency = {}

  nodes.forEach(n => {
    inDegree[n.id] = 0
    adjacency[n.id] = []
  })

  edges.forEach(e => {
    if (adjacency[e.source]) {
      adjacency[e.source].push(e.target)
      if (inDegree[e.target] !== undefined) {
        inDegree[e.target]++
      }
    }
  })

  const queue = nodes.filter(n => inDegree[n.id] === 0)
  const result = []

  while (queue.length > 0) {
    const node = queue.shift()
    result.push(node)

    adjacency[node.id].forEach(targetId => {
      inDegree[targetId]--
      if (inDegree[targetId] === 0) {
        const targetNode = nodes.find(n => n.id === targetId)
        if (targetNode) queue.push(targetNode)
      }
    })
  }

  return result
}

/**
 * 检测图中是否存在环
 * @param {Node[]} nodes - 节点列表
 * @param {Edge[]} edges - 边列表
 * @returns {boolean} 是否存在环
 */
export function hasCycle(nodes, edges) {
  const WHITE = 0, GRAY = 1, BLACK = 2
  const color = {}
  nodes.forEach(n => color[n.id] = WHITE)

  function dfs(nodeId) {
    color[nodeId] = GRAY
    const outgoing = getOutgoingNodes(nodeId, nodes, edges)
    for (const next of outgoing) {
      if (color[next.id] === GRAY) return true
      if (color[next.id] === WHITE && dfs(next.id)) return true
    }
    color[nodeId] = BLACK
    return false
  }

  for (const node of nodes) {
    if (color[node.id] === WHITE && dfs(node.id)) return true
  }

  return false
}
