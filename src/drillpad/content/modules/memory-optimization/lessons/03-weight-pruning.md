# Pruning: Structural vs Unstructured, Sparsity Patterns

## Unstructured Pruning (Remove Individual Weights)

Remove weights where |w| < threshold. Sparse matrix: most entries are zero.

```
Dense: 70B weights, all stored
Pruned (50%): 35B non-zero weights
Storage: 17.5 GB (with sparse format overhead ~25% → 22 GB)

Speedup: 1.5–2x on sparse matmul (depends on hardware support)
Accuracy: ~1% loss if you retrain

Challenge: sparse matmul is slow on dense hardware (GPUs don't optimize sparse ops well).
```

---

## Structured Pruning (Remove Channels/Heads)

Remove entire output channels or attention heads. Dense matrix, smaller.

```
70B model, 32 heads per attention layer
Remove 8 heads (25%): 52.5B model (25% smaller)
Speedup: 1.25x (clean, dense matmul)
Accuracy: ~2% loss

No special hardware needed (standard dense matmul, just smaller).
```

---

## Magnitude Pruning vs Learned Pruning

Magnitude: remove weights with smallest |w| (simple, no training).
Learned: train a mask/gate to learn which weights matter (better, requires finetuning).

---

## Q&A

**Recall 1:** Why is structured pruning easier to deploy than unstructured?

*Answer:* Structured removes entire channels (columns of matrix), keeping it dense. GPUs optimize dense matmul. Unstructured removes scattered weights, creating sparse matrix; GPUs don't have efficient sparse kernels, speedup is minimal.

**Numeric 1:** 70B model, 25% structured pruning. H100 speedup?

*Working:* 1.25x speedup (25% fewer FLOPs). 70B / (3 TFLOPS) = 23 s → 18.4 s.

