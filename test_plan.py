# test_plan.py
from caainp_csm import Graph4F, create_simple_plan, update_state_with_node

if __name__ == "__main__":
    g = Graph4F()
    text = "지금 401호에서 410호 들렀다가 420호로 가고 싶어요"
    plan = create_simple_plan(text, g, start_room=401)

    print("생성된 Plan JSON:")
    import json
    print(json.dumps(plan.to_json(), ensure_ascii=False, indent=2))

    # 상태 업데이트 시뮬레이션
    # 실제로는 CVM에서 current_node를 계속 보내준다고 생각하면 됨
    for node in plan.steps[0].route_nodes:
        print(f"current_node = {node}")
        update_state_with_node(plan, current_node=node, stay_frames=2)
        print("current_step:", plan.current_step, "steps_status:", plan.steps_status)
