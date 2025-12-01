# plan_csm.py
from typing import List, Dict, Any
from dataclasses import dataclass, field
from graph_4f import Graph4F

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
    # target_nodes 캐시 (상태 머신에서 사용)
    step_targets: Dict[int, List[int]] = field(default_factory=dict)
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

def create_simple_plan(text: str, g: Graph4F, start_room: int) -> PlanState:
    """
    아주 단순한 버전:
    - 문장에서 'XXX호'들만 찾고
    - 첫 번째 번호 = 경유 (optional), 마지막 번호 = 최종 목적지 라고 가정
    - 제약: 일단 엘리베이터/계단 제약 없음
    """
    import re
    room_nums = [int(m.group(1)) for m in re.finditer(r"(\d{3,4})호", text)]
    if not room_nums:
        raise ValueError("방 번호를 찾지 못했습니다.")

    # 시작 방도 포함해서 경유/도착 구성 (아주 단순한 예)
    all_rooms = [start_room] + room_nums

    constraints = Constraints(
        use_elevator_only=False,
        avoid_stairs=False,
        forbidden_nodes=[],
        via_rooms=room_nums[:-1],  # 마지막을 제외한 것들을 경유로
    )

    steps: List[Step] = []
    for i in range(1, len(all_rooms)):
        src_room = all_rooms[i - 1]
        dst_room = all_rooms[i]
        src_node = g.room_nodes.get(src_room)
        dst_node = g.room_nodes.get(dst_room)
        if src_node is None or dst_node is None:
            raise ValueError(f"room {src_room} or {dst_room} not found in graph")

        # 경로 계산
        route = g.bfs_shortest_path(
            start=src_node,
            targets=[dst_node],
            use_elevator_only=constraints.use_elevator_only,
            avoid_stairs=constraints.avoid_stairs,
            forbidden_nodes=constraints.forbidden_nodes,
        )

        step = Step(
            step_id=i,
            goal_type="ROOM",
            goal_room=dst_room,
            allowed_moves=["CORRIDOR", "ELEVATOR", "STAIRS"],
            description_ko=f"{src_room}에서 {dst_room}호 강의실 앞까지 이동",
            target_nodes=[dst_node],
            route_nodes=route,
        )
        steps.append(step)

    steps_status = {s.step_id: ("IN_PROGRESS" if s.step_id == 1 else "PENDING") for s in steps}
    step_targets = {s.step_id: s.target_nodes for s in steps}

    return PlanState(
        constraints=constraints,
        steps=steps,
        current_step=1,
        steps_status=steps_status,
        step_targets=step_targets,
    )

def update_state_with_node(plan: PlanState, current_node: int, stay_frames: int = 5) -> None:
    """
    CVM에서 매 프레임 current_node를 넣어줄 때마다 호출된다고 가정.
    stay_frames: 목표 노드에 N프레임 연속으로 있으면 그 step을 완료.
    """
    cur_id = plan.current_step
    if cur_id not in plan.steps_status:
        return  # 모든 step 완료

    status = plan.steps_status[cur_id]
    if status == "DONE":
        return

    targets = plan.step_targets.get(cur_id, [])
    if current_node in targets:
        plan.in_target_count += 1
        if plan.in_target_count >= stay_frames:
            # step 완료
            plan.steps_status[cur_id] = "DONE"
            plan.current_step += 1
            plan.in_target_count = 0
            # 다음 step이 있으면 IN_PROGRESS로 변경
            if plan.current_step in plan.steps_status:
                plan.steps_status[plan.current_step] = "IN_PROGRESS"
    else:
        # 목표에서 벗어나 있으면 카운터 리셋
        plan.in_target_count = 0
