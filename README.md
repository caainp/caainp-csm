# How to use
---
## Run
`python3 test_plan.py`

---
## Expect Output
```
생성된 Plan JSON:
{
  "constraints": {
    "use_elevator_only": false,
    "avoid_stairs": false,
    "forbidden_nodes": [],
    "via_rooms": [
      401,
      410
    ]
  },
  "steps": [
    {
      "step_id": 1,
      "goal_type": "ROOM",
      "goal_room": 401,
      "allowed_moves": [
        "CORRIDOR",
        "ELEVATOR",
        "STAIRS"
      ],
      "description_ko": "401에서 401호 강의실 앞까지 이동",
      "target_nodes": [
        401
      ],
      "route_nodes": [
        401
      ]
    },
    {
      "step_id": 2,
      "goal_type": "ROOM",
      "goal_room": 410,
      "allowed_moves": [
        "CORRIDOR",
        "ELEVATOR",
        "STAIRS"
      ],
      "description_ko": "401에서 410호 강의실 앞까지 이동",
      "target_nodes": [
        410
      ],
      "route_nodes": [
        401,
        4102,
        4201,
        4101,
        410
      ]
    },
    {
      "step_id": 3,
      "goal_type": "ROOM",
      "goal_room": 420,
      "allowed_moves": [
        "CORRIDOR",
        "ELEVATOR",
        "STAIRS"
      ],
      "description_ko": "410에서 420호 강의실 앞까지 이동",
      "target_nodes": [
        420
      ],
      "route_nodes": [
        410,
        411,
        4202,
        4103,
        420
      ]
    }
  ],
  "current_step": 1,
  "steps_status": [
    {
      "step_id": 1,
      "status": "IN_PROGRESS"
    },
    {
      "step_id": 2,
      "status": "PENDING"
    },
    {
      "step_id": 3,
      "status": "PENDING"
    }
  ]
}
current_node = 401
current_step: 1 steps_status: {1: 'IN_PROGRESS', 2: 'PENDING', 3: 'PENDING'}
```
