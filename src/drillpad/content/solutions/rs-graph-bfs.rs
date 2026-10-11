use std::collections::VecDeque;

fn bfs_core(adj: &[Vec<usize>], start: usize) -> (Vec<Option<usize>>, Vec<Option<usize>>, Vec<usize>) {
    let n = adj.len();
    let mut dist: Vec<Option<usize>> = vec![None; n];
    let mut parent: Vec<Option<usize>> = vec![None; n];
    let mut order = Vec::new();
    if start >= n {
        return (dist, parent, order);
    }
    let mut queue = VecDeque::new();
    dist[start] = Some(0);
    queue.push_back(start);
    while let Some(u) = queue.pop_front() {
        order.push(u);
        let du = dist[u].unwrap();
        for &v in &adj[u] {
            if v < n && dist[v].is_none() {
                dist[v] = Some(du + 1);
                parent[v] = Some(u);
                queue.push_back(v);
            }
        }
    }
    (dist, parent, order)
}

fn bfs_distances(adj: &[Vec<usize>], start: usize) -> Vec<Option<usize>> {
    bfs_core(adj, start).0
}

fn bfs_order(adj: &[Vec<usize>], start: usize) -> Vec<usize> {
    bfs_core(adj, start).2
}

fn shortest_path(adj: &[Vec<usize>], from: usize, to: usize) -> Option<Vec<usize>> {
    if from >= adj.len() || to >= adj.len() {
        return None;
    }
    let (dist, parent, _) = bfs_core(adj, from);
    dist[to]?;
    let mut path = vec![to];
    let mut cur = to;
    while cur != from {
        cur = parent[cur]?;
        path.push(cur);
    }
    path.reverse();
    Some(path)
}
