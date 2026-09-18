#!/bin/bash
set -euo pipefail

MODEL="${1:-mymodel}"
MODELSPATH="${2:-/tmp/mymodels}"

echo "Loading model $MODEL to $MODELSPATH"
om models get $MODEL $MODELSPATH

echo "Running vllm serve for $MODEL in $MODELSPATH"
cd $MODELSPATH

TEMPLATE="{% for message in messages %}
{% if message['role'] == 'system' %}<<SYS>>{{ message['content'] }}<</SYS>>{% endif %}
{% if message['role'] == 'user' %}### User: {{ message['content'] }}{% endif %}
{% if message['role'] == 'assistant' %}### Assistant: {{ message['content'] }}{% endif %}
{% endfor %}
{% if add_generation_prompt %}### Assistant:{% endif %}"

vllm serve $MODEL \
  --gpu-memory-utilization 0.1 \
  --chat-template "$TEMPLATE"
