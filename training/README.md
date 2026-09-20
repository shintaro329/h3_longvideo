# Training Extension Point

The current repository intentionally does not train a model. This directory reserves the post-training boundary for a frozen MiniMax H3 Base continuation adapter.

Planned ownership:

```text
training/
├── configs/       # Versioned training configuration templates
├── src/           # Dataset, continuation-pair construction, and trainer modules
├── scripts/       # Reproducible training entry points
└── README.md      # Contract and evidence requirements
```

The first supported research direction should be a continuation LoRA. H3 Base remains frozen; each sample is a legal H3-aligned window with the previous generated tail, persistent references, local storyboard text, and a current target window. The training interface must preserve the inference `ChunkSpec`, reference order, and manifest fields.

Before adding implementation, document the dataset license, sample manifest, adapter insertion points, checkpoint format, loss terms, evaluation splits, and rollback path. No claim of improved consistency should be made without boundary-level and end-to-end evidence.

