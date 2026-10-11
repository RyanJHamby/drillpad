# Backpropagation & Autodiff

## Gradient Descent

```
Goal: minimize loss (error)

Loss = sum of (predicted - actual)^2

Gradient: direction of steepest increase
  ∇Loss = [∂Loss/∂w1, ∂Loss/∂w2, ..., ∂Loss/∂wN]

Update: move opposite to gradient
  w_new = w_old - learning_rate * ∇Loss
  
Intuition: roll downhill to minimize loss
```

## Backpropagation

```
Forward pass:
  x → [linear] → [relu] → [linear] → [softmax] → loss

Backward pass:
  loss.grad = 1
  softmax.grad = (dLoss/dout_softmax)
  linear2.grad = softmax.grad * (dout_softmax/dw2)
  relu.grad = linear2.grad * (drelu/dout_relu)
  linear1.grad = relu.grad * (dout_relu/dw1)

Chain rule: dL/dw1 = dL/dout * dout/dw1

Result: gradient for each weight
```

## Automatic Differentiation (autodiff)

```
Framework: PyTorch, TensorFlow

Code:
  x = tensor([1, 2, 3], requires_grad=True)
  y = x * 2
  z = y.sum()
  z.backward()  ← autodiff computes gradients
  print(x.grad)  → [2, 2, 2]

How it works:
  ├─ Record operations: build computation graph
  ├─ Reverse mode (backprop): traverse graph backward
  ├─ Compute ∂z/∂x via chain rule
  └─ Efficient: O(N) params, O(N) memory

Modes:
  ├─ Forward mode: ∂f/∂x (rare, used for Jacobian-vector)
  ├─ Reverse mode: ∂loss/∂all_params (standard)
  └─ Default: reverse (better for deep networks)
```

## Optimizers

```
SGD (Stochastic Gradient Descent):
  w ← w - lr * ∇loss
  Fast but noisy (slow convergence)

Momentum:
  v = momentum * v + ∇loss
  w ← w - lr * v
  Accelerates convergence, reduces oscillation

Adam (Adaptive):
  Combines momentum + adaptive learning rates
  Works well for most problems
  Default choice
  
Learning rate schedule:
  ├─ Constant: lr = 0.001 (simple)
  ├─ Decay: lr = 0.001 * 0.99^epoch (gradual)
  ├─ Cosine annealing: lr = 0.001 * cos(epoch/max_epochs)
  └─ Warmup: start low, ramp to peak, decay
```

## Batch Size Effects

```
Small batch (size=1):
  ├─ Noisy gradients (high variance)
  ├─ Updates frequent (fast iterations)
  ├─ Generalization good (noise acts as regularization)
  └─ Slow wall-clock time (inefficient GPU utilization)

Large batch (size=1024):
  ├─ Stable gradients (low variance)
  ├─ Updates infrequent (slow convergence)
  ├─ Generalization worse (less noise)
  └─ Fast wall-clock time (GPU fully utilized)

Rule of thumb:
  ├─ Use largest batch that fits in memory
  ├─ Scale learning rate with batch size
  └─ Typical: 32-256 for GPUs
```

---

## Interview Checklist

- [ ] Chain rule: dL/dw = dL/dout * dout/dw
- [ ] Backprop: reverse-mode autodiff
- [ ] Optimizers: SGD, momentum, Adam
- [ ] Learning rate: constant, decay, warmup
- [ ] Batch size: tradeoff between noise and GPU utilization

## Common Wrong Answers

- ❌ "All gradients are computed independently" — chain rule required
- ❌ "Larger batch always better" — generalization suffers
- ❌ "Fixed learning rate for all epochs" — should decay over time
