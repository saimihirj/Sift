"""Sift Brain — intelligence layer for the Sift platform.

Provides:
  knowledge_graph/  — dynamic domain updater, ChromaDB embedder, entity graph, hybrid retriever
  decision_layer/   — intelligent query router and context builder
  training/         — dataset builder, LoRA/QLoRA fine-tuner, hypertuner, evaluator
  serving/          — OpenAI-compatible local model server and adapter registry
"""
