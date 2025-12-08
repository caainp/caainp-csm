# graph_4f.py
import pandas as pd
from typing import Dict, List, Set
from pathlib import Path
import importlib.resources

def _get_default_csv_path():
    """패키지 내부의 CSV 파일 경로를 반환"""
    try:
        csv_path = importlib.resources.path("caainp_csm.data", "ai_4f_node_map_fixed_embeded.csv")
        path = csv_path.__enter__()
        return str(path)
    except (AttributeError, ModuleNotFoundError, TypeError, ImportError):
        # fallback
        return str(Path(__file__).parent / "data" / "ai_4f_node_map_fixed_embeded.csv")

class Graph4F:
    def __init__(self, csv_path: str = None):
        if csv_path is None:
            csv_path = _get_default_csv_path()
        self.df = pd.read_csv(csv_path)
        # 4층만 사용
        self.df = self.df[self.df["floor"] == 4]
        # 기본 자료구조
        self.adj: Dict[int, List[int]] = {}
        self.node_type: Dict[int, str] = {}
        self.room_nodes: Dict[int, int] = {}  # 예: 401 -> 401 (ROOM 노드)
        self._build()

    def _build(self):
        for _, row in self.df.iterrows():
            node_id = int(row["node_id"])
            self.node_type[node_id] = str(row["type"])
            # neighbors: '402;4102;4112' 형식
            neighbors_raw = str(row["neighbors"])
            if neighbors_raw == "nan":
                neighbors = []
            else:
                neighbors = [int(x) for x in neighbors_raw.split(";") if x]

            # 양방향 그래프 구성
            if node_id not in self.adj:
                self.adj[node_id] = []
            for nb in neighbors:
                self.adj[node_id].append(nb)
                if nb not in self.adj:
                    self.adj[nb] = []
                if node_id not in self.adj[nb]:
                    self.adj[nb].append(node_id)

            # description에서 방 번호 추출 (ROOM일 때만)
            desc = str(row["description"])
            # 예: "401호 강의실"
            import re
            m = re.search(r"(\d{3,4})호", desc)
            if m and str(row["type"]) == "ROOM":
                room_num = int(m.group(1))
                self.room_nodes[room_num] = node_id

    def filtered_adj(self,
                     use_elevator_only: bool,
                     avoid_stairs: bool,
                     forbidden_nodes: List[int]) -> Dict[int, List[int]]:
        """제약을 반영한 adjacency 리턴"""
        forbidden: Set[int] = set(forbidden_nodes)
        # 계단 금지면 STAIRS 노드도 금지
        if avoid_stairs or use_elevator_only:
            for n, t in self.node_type.items():
                if t == "STAIRS":
                    forbidden.add(n)

        new_adj: Dict[int, List[int]] = {}
        for n, nbrs in self.adj.items():
            if n in forbidden:
                continue
            new_adj[n] = [nb for nb in nbrs if nb not in forbidden]
        return new_adj

    def bfs_shortest_path(self,
                          start: int,
                          targets: List[int],
                          use_elevator_only: bool = False,
                          avoid_stairs: bool = False,
                          forbidden_nodes: List[int] = None) -> List[int]:
        """start에서 targets 중 하나까지 최단 경로 (노드 리스트)"""
        if forbidden_nodes is None:
            forbidden_nodes = []
        target_set = set(targets)
        adj = self.filtered_adj(use_elevator_only, avoid_stairs, forbidden_nodes)

        from collections import deque
        q = deque()
        q.append(start)
        visited = {start: None}

        while q:
            cur = q.popleft()
            if cur in target_set:
                # 경로 복원
                path = [cur]
                while visited[cur] is not None:
                    cur = visited[cur]
                    path.append(cur)
                path.reverse()
                return path

            for nb in adj.get(cur, []):
                if nb not in visited:
                    visited[nb] = cur
                    q.append(nb)

        return []  # 경로 없음
