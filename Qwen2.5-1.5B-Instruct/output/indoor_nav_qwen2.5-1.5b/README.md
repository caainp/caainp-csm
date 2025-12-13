---
library_name: peft
license: other
base_model: /root/workspace/Qwen2.5-1.5B-Instruct
tags:
- llama-factory
- lora
- generated_from_trainer
model-index:
- name: indoor_nav_qwen2.5-1.5b
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# indoor_nav_qwen2.5-1.5b

This model is a fine-tuned version of [/root/workspace/Qwen2.5-1.5B-Instruct](https://huggingface.co//root/workspace/Qwen2.5-1.5B-Instruct) on the indoor_nav dataset.

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 0.0001
- train_batch_size: 4
- eval_batch_size: 8
- seed: 42
- gradient_accumulation_steps: 4
- total_train_batch_size: 16
- optimizer: Use adamw_torch with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- lr_scheduler_warmup_ratio: 0.03
- num_epochs: 2.0
- mixed_precision_training: Native AMP

### Training results



### Framework versions

- PEFT 0.15.2
- Transformers 4.52.4
- Pytorch 2.5.0+cu124
- Datasets 3.6.0
- Tokenizers 0.21.1