# csm_cached.py
from __future__ import annotations

import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Hashable, List, Optional, Set, Tuple

try:
    # 패키지 내부에서 import 할 때
    from .graph_4f import Graph4F
except ImportError:  # pragma: no cover
    # 단일 파일로 직접 실행/테스트할 때
    from graph_4f import Graph4F


# -----------------------------------------------------------------------------
# Data models
# -----------------------------------------------------------------------------

@dataclass
class Constraints:
    use_elevator_only: bool = False
    avoid_stairs: bool = False
    forbidden_nodes: List[int] = field(default_factory=list)
    via_rooms: List[int] = field(default_factory=list)


@dataclass
class Step:
    step_id: int
    goal_type: str  # "ROOM"
    goal_room: int
    allowed_moves: List[str]
    description_ko: str
    target_nodes: List[int]
    route_nodes: List[int] = field(default_factory=list)


@dataclass
class PlanState:
    constraints: Constraints
    steps: List[Step]
    current_step: int = 1
    steps_status: Dict[int, str] = field(default_factory=dict)  # step_id -> "IN_PROGRESS"/"PENDING"/"DONE"

    # 상태 머신에서 바로 쓰는 target_nodes 캐시
    step_targets: Dict[int, List[int]] = field(default_factory=dict)

    # 매 프레임 membership check를 빠르게 하기 위한 set 캐시
    # JSON으로 내보낼 필요가 없으므로 to_json에서는 제외한다.
    step_target_sets: Dict[int, Set[int]] = field(default_factory=dict, repr=False)

    # target 노드에 머문 프레임 수
    in_target_count: int = 0

    def to_json(self) -> Dict[str, Any]:
        return {
            "constraints": {
                "use_elevator_only": self.constraints.use_elevator_only,
                "avoid_stairs": self.constraints.avoid_stairs,
                "forbidden_nodes": self.constraints.forbidden_nodes,
                "via_rooms": self.constraints.via_rooms,
            },
            "steps": [
                {
                    "step_id": s.step_id,
                    "goal_type": s.goal_type,
                    "goal_room": s.goal_room,
                    "allowed_moves": s.allowed_moves,
                    "description_ko": s.description_ko,
                    "target_nodes": s.target_nodes,
                    "route_nodes": s.route_nodes,
                }
                for s in self.steps
            ],
            "current_step": self.current_step,
            "steps_status": [
                {"step_id": sid, "status": st}
                for sid, st in self.steps_status.items()
            ],
        }


# -----------------------------------------------------------------------------
# Cache layer
# -----------------------------------------------------------------------------

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expired: int = 0

    def to_json(self) -> Dict[str, int]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "evictions": self.evictions,
            "expired": self.expired,
        }


@dataclass
class _CacheEntry:
    value: Any
    created_at: float


class _LRUTTLCache:
    """
    작은 범용 LRU + TTL 캐시.

    - maxsize <= 0 이면 캐시가 사실상 비활성화된다.
    - ttl_seconds=None 이면 만료 없이 LRU만 적용한다.
    - thread-safe 하게 RLock을 사용한다.
    """

    def __init__(self, maxsize: int = 1024, ttl_seconds: Optional[float] = None) -> None:
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._store: "OrderedDict[Hashable, _CacheEntry]" = OrderedDict()
        self._stats = CacheStats()
        self._lock = RLock()

    def get(self, key: Hashable) -> Optional[Any]:
        if self.maxsize <= 0:
            self._stats.misses += 1
            return None

        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if self.ttl_seconds is not None and now - entry.created_at > self.ttl_seconds:
                self._store.pop(key, None)
                self._stats.expired += 1
                self._stats.misses += 1
                return None

            self._store.move_to_end(key)
            self._stats.hits += 1
            return entry.value

    def set(self, key: Hashable, value: Any) -> None:
        if self.maxsize <= 0:
            return

        with self._lock:
            self._store[key] = _CacheEntry(value=value, created_at=time.monotonic())
            self._store.move_to_end(key)
            self._stats.sets += 1

            while len(self._store) > self.maxsize:
                self._store.popitem(last=False)
                self._stats.evictions += 1

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._stats = CacheStats()

    def stats(self) -> Dict[str, int]:
        with self._lock:
            data = self._stats.to_json()
            data["size"] = len(self._store)
            data["maxsize"] = self.maxsize
            return data


class PlanCache:
    """
    plan_csm 전용 캐시 묶음.

    캐시 대상:
    1. 텍스트에서 추출한 방 번호 목록
    2. room 번호 -> graph node 변환 결과
    3. BFS shortest path 결과

    주의:
    Graph4F 객체의 topology가 실행 중 바뀌면, 기존 route 캐시는 낡은 값이 된다.
    그 경우 clear()를 호출하거나 create_simple_plan(..., graph_cache_id="새버전")처럼
    graph_cache_id를 바꿔서 사용한다.
    """

    def __init__(
        self,
        *,
        max_text_cache: int = 256,
        max_room_node_cache: int = 2048,
        max_route_cache: int = 4096,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        self.text_cache = _LRUTTLCache(maxsize=max_text_cache, ttl_seconds=ttl_seconds)
        self.room_node_cache = _LRUTTLCache(maxsize=max_room_node_cache, ttl_seconds=ttl_seconds)
        self.route_cache = _LRUTTLCache(maxsize=max_route_cache, ttl_seconds=ttl_seconds)

    def clear(self) -> None:
        self.text_cache.clear()
        self.room_node_cache.clear()
        self.route_cache.clear()

    def stats(self) -> Dict[str, Dict[str, int]]:
        return {
            "text_cache": self.text_cache.stats(),
            "room_node_cache": self.room_node_cache.stats(),
            "route_cache": self.route_cache.stats(),
        }

    def parse_room_numbers(self, text: str) -> List[int]:
        key = _normalize_text_key(text)
        cached = self.text_cache.get(key)
        if cached is not None:
            return list(cached)

        room_nums = tuple(_parse_room_numbers(text))
        self.text_cache.set(key, room_nums)
        return list(room_nums)

    def get_room_node(self, g: Graph4F, room: int, graph_key: Hashable) -> Optional[int]:
        key = (graph_key, int(room))
        cached = self.room_node_cache.get(key)
        if cached is not None:
            return int(cached)

        node = g.room_nodes.get(int(room))
        if node is not None:
            self.room_node_cache.set(key, int(node))
        return node

    def get_bfs_shortest_path(
        self,
        *,
        g: Graph4F,
        graph_key: Hashable,
        start: int,
        targets: List[int],
        use_elevator_only: bool,
        avoid_stairs: bool,
        forbidden_nodes: List[int],
    ) -> List[int]:
        key = _make_route_cache_key(
            graph_key=graph_key,
            start=start,
            targets=targets,
            use_elevator_only=use_elevator_only,
            avoid_stairs=avoid_stairs,
            forbidden_nodes=forbidden_nodes,
        )

        cached = self.route_cache.get(key)
        if cached is not None:
            return list(cached)

        route = g.bfs_shortest_path(
            start=int(start),
            targets=[int(t) for t in targets],
            use_elevator_only=use_elevator_only,
            avoid_stairs=avoid_stairs,
            forbidden_nodes=[int(n) for n in forbidden_nodes],
        )

        if route is None:
            raise ValueError(f"경로를 찾지 못했습니다. start={start}, targets={targets}")

        route_tuple = tuple(int(n) for n in route)
        self.route_cache.set(key, route_tuple)
        return list(route_tuple)


# 모듈 기본 캐시.
# create_simple_plan(..., cache=None)을 넘기면 캐시를 끌 수 있다.
DEFAULT_PLAN_CACHE = PlanCache()


# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------

def clear_default_plan_cache() -> None:
    DEFAULT_PLAN_CACHE.clear()


def get_default_plan_cache_stats() -> Dict[str, Dict[str, int]]:
    return DEFAULT_PLAN_CACHE.stats()


# -----------------------------------------------------------------------------
# Plan creation
# -----------------------------------------------------------------------------

def create_simple_plan(
    text: str,
    g: Graph4F,
    start_room: int,
    *,
    cache: Optional[PlanCache] = DEFAULT_PLAN_CACHE,
    graph_cache_id: Optional[Hashable] = None,
) -> PlanState:
    """
    아주 단순한 버전 + 캐시 적용 버전.

    동작:
    - 문장에서 'XXX호' 또는 'XXXX호'를 찾는다.
    - 첫 번째부터 마지막 전까지 = 경유 방
    - 마지막 번호 = 최종 목적지
    - 각 구간별 BFS shortest path를 계산한다.

    캐시:
    - 방 번호 파싱 결과 캐시
    - room 번호 -> node 변환 캐시
    - BFS route 캐시

    graph_cache_id:
    - 같은 Graph4F 객체를 계속 쓰면 생략해도 된다. 기본값은 id(g)다.
    - 그래프 topology가 바뀌는 구조라면 버전 문자열/숫자를 넣는 것을 권장한다.
      예: graph_cache_id="4f-v2026-06-14"
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text가 비어 있습니다.")

    graph_key = graph_cache_id if graph_cache_id is not None else _default_graph_cache_key(g)

    if cache is not None:
        room_nums = cache.parse_room_numbers(text)
    else:
        room_nums = _parse_room_numbers(text)

    if not room_nums:
        raise ValueError("방 번호를 찾지 못했습니다.")

    all_rooms = [int(start_room)] + [int(room) for room in room_nums]

    constraints = Constraints(
        use_elevator_only=False,
        avoid_stairs=False,
        forbidden_nodes=[],
        via_rooms=room_nums[:-1],
    )

    steps: List[Step] = []
    for i in range(1, len(all_rooms)):
        src_room = all_rooms[i - 1]
        dst_room = all_rooms[i]

        src_node = _get_room_node(g, src_room, cache=cache, graph_key=graph_key)
        dst_node = _get_room_node(g, dst_room, cache=cache, graph_key=graph_key)
        if src_node is None or dst_node is None:
            raise ValueError(f"room {src_room} or {dst_room} not found in graph")

        if cache is not None:
            route = cache.get_bfs_shortest_path(
                g=g,
                graph_key=graph_key,
                start=src_node,
                targets=[dst_node],
                use_elevator_only=constraints.use_elevator_only,
                avoid_stairs=constraints.avoid_stairs,
                forbidden_nodes=constraints.forbidden_nodes,
            )
        else:
            route = g.bfs_shortest_path(
                start=src_node,
                targets=[dst_node],
                use_elevator_only=constraints.use_elevator_only,
                avoid_stairs=constraints.avoid_stairs,
                forbidden_nodes=constraints.forbidden_nodes,
            )
            if route is None:
                raise ValueError(f"경로를 찾지 못했습니다. start={src_node}, targets={[dst_node]}")
            route = [int(n) for n in route]

        step = Step(
            step_id=i,
            goal_type="ROOM",
            goal_room=dst_room,
            allowed_moves=["CORRIDOR", "ELEVATOR", "STAIRS"],
            description_ko=f"{src_room}에서 {dst_room}호 강의실 앞까지 이동",
            target_nodes=[int(dst_node)],
            route_nodes=route,
        )
        steps.append(step)

    steps_status = {
        s.step_id: ("IN_PROGRESS" if s.step_id == 1 else "PENDING")
        for s in steps
    }
    step_targets = {s.step_id: list(s.target_nodes) for s in steps}
    step_target_sets = {s.step_id: {int(n) for n in s.target_nodes} for s in steps}

    return PlanState(
        constraints=constraints,
        steps=steps,
        current_step=1,
        steps_status=steps_status,
        step_targets=step_targets,
        step_target_sets=step_target_sets,
    )


# -----------------------------------------------------------------------------
# State update
# -----------------------------------------------------------------------------

def update_state_with_node(
    plan: PlanState,
    current_node: int,
    stay_frames: int = 5,
    arrival_state: Optional[str] = None,
    target_visibility: Optional[Dict[str, Any]] = None,
) -> None:
    """
    CVM에서 매 프레임 current_node를 넣어줄 때마다 호출한다고 가정한다.

    완료 조건:
    1. current_node가 현재 step의 target node에 stay_frames 프레임 연속 머무름
    2. 또는 arrival_state == "IN_SIGHT" 이고 target_visibility의 target_node가
       현재 step의 target node와 일치하는 상태가 stay_frames 프레임 연속 유지됨
    """
    if stay_frames <= 0:
        raise ValueError("stay_frames는 1 이상이어야 합니다.")

    cur_id = plan.current_step
    if cur_id not in plan.steps_status:
        return  # 모든 step 완료

    status = plan.steps_status[cur_id]
    if status == "DONE":
        return

    target_set = _get_step_target_set(plan, cur_id)
    reached_target = int(current_node) in target_set or (
        arrival_state == "IN_SIGHT"
        and _target_visible_for_step(target_visibility, target_set)
    )

    if reached_target:
        plan.in_target_count += 1
        if plan.in_target_count >= stay_frames:
            plan.steps_status[cur_id] = "DONE"
            plan.current_step += 1
            plan.in_target_count = 0

            if plan.current_step in plan.steps_status:
                plan.steps_status[plan.current_step] = "IN_PROGRESS"
    else:
        plan.in_target_count = 0


# -----------------------------------------------------------------------------
# Internal utilities
# -----------------------------------------------------------------------------

def _parse_room_numbers(text: str) -> List[int]:
    return [int(m.group(1)) for m in re.finditer(r"(\d{3,4})호", text)]


def _normalize_text_key(text: str) -> str:
    # 공백 차이 때문에 캐시가 쓸데없이 갈라지는 것을 줄인다.
    return " ".join(text.strip().split())


def _default_graph_cache_key(g: Graph4F) -> Hashable:
    # graph 객체가 cache_id/version 속성을 제공하면 우선 사용한다.
    # 없으면 현재 객체 identity를 사용한다.
    return getattr(g, "cache_id", None) or getattr(g, "version", None) or id(g)


def _get_room_node(
    g: Graph4F,
    room: int,
    *,
    cache: Optional[PlanCache],
    graph_key: Hashable,
) -> Optional[int]:
    if cache is not None:
        return cache.get_room_node(g, room, graph_key)
    node = g.room_nodes.get(int(room))
    return int(node) if node is not None else None


def _make_route_cache_key(
    *,
    graph_key: Hashable,
    start: int,
    targets: List[int],
    use_elevator_only: bool,
    avoid_stairs: bool,
    forbidden_nodes: List[int],
) -> Tuple[Any, ...]:
    # BFS 목표는 보통 set처럼 쓰이므로 정렬/중복제거해서 key 안정성을 높인다.
    target_key = tuple(sorted({int(t) for t in targets}))
    forbidden_key = tuple(sorted({int(n) for n in forbidden_nodes}))
    return (
        graph_key,
        int(start),
        target_key,
        bool(use_elevator_only),
        bool(avoid_stairs),
        forbidden_key,
    )


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _target_visible_for_step(
    target_visibility: Optional[Dict[str, Any]],
    target_set: Set[int],
) -> bool:
    if not target_visibility or not target_visibility.get("visible"):
        return False

    visible_target = _int_or_none(target_visibility.get("target_node"))
    if visible_target is None:
        return False

    return visible_target in target_set


def _get_step_target_set(plan: PlanState, step_id: int) -> Set[int]:
    cached = plan.step_target_sets.get(step_id)
    if cached is not None:
        return cached

    target_set = {int(target) for target in plan.step_targets.get(step_id, [])}
    plan.step_target_sets[step_id] = target_set
    return target_set


__all__ = [
    "Constraints",
    "Step",
    "PlanState",
    "PlanCache",
    "DEFAULT_PLAN_CACHE",
    "create_simple_plan",
    "update_state_with_node",
    "clear_default_plan_cache",
    "get_default_plan_cache_stats",
]
