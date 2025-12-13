#!/usr/bin/env python
from llamafactory.chat import ChatModel

def main():
    # 1) 베이스 모델 + LoRA 어댑터 경로 설정
    args = dict(
        model_name_or_path="/root/workspace/Qwen2.5-1.5B-Instruct",
        adapter_name_or_path="/root/workspace/Qwen2.5-1.5B-Instruct/output/indoor_nav_qwen2.5-1.5b/checkpoint-250",
        stage="sft",
        finetuning_type="lora",
        template="qwen",
        quantization_bit=4,   # 학습 때 4bit였다면 유지
    )
    chat_model = ChatModel(args)

    # 2) 테스트용 입력 문장
    user_text = "지금 4층 상단 여자 화장실에 있는데 4층 중앙 엘리베이터로 가고 싶어요"

    messages = [
        {"role": "user", "content": user_text}
    ]

    # 3) 모델 호출
    responses = chat_model.chat(messages, max_new_tokens=256)

    # 4) 결과 출력
    for r in responses:
        print("=== MODEL OUTPUT ===")
        print(r.response)

if __name__ == "__main__":
    main()
