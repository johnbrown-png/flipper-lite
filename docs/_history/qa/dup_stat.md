# Dup Stat Equations and Explanation

The step-level hybrid duplicate score is:

$$
H_i = 0.5A_i + 0.3B_i + 0.2C_i
$$

Where:

$$
A_i = S_i \cdot \frac{1}{n_i}\sum_{k=1}^{n_i}\max\left(0,1-\frac{d_{ik}}{W}\right)
$$

$$
B_i = S_i \cdot \max(0, Z_{\text{context}}(A_i))
$$

$$
C_i = \Pr(d \le 3\mid \text{duplicate links in local context})
$$

And shrinkage support is:

$$
S_i=\frac{n_i}{n_i+k}
$$

## Meaning of each key term

1. $d_{ik}$

Distance between small step $i$ and another step $j$ that shares the same video (for duplicate link $k$):

$$
d_{ik}=\left|\text{small\_step\_num\_global}_i-\text{small\_step\_num\_global}_j\right|
$$

Interpretation:

- $d=1$: adjacent steps (higher UX duplicate-fatigue risk)
- Larger $d$: farther apart (lower immediate fatigue risk)

2. $W$

Distance window hyperparameter (for example $W=10$). It controls how quickly the proximity penalty decays.

Inside $A_i$, the term

$$
\max\left(0,1-\frac{d}{W}\right)
$$

behaves as:

- $d=0 \Rightarrow 1$
- $d=W \Rightarrow 0$
- $d>W \Rightarrow 0$ (clipped by max)

So $W$ defines what counts as near-duplicate in practice.

3. $S_i$

Support shrinkage factor:

$$
S_i=\frac{n_i}{n_i+k}
$$

where:

- $n_i$ = number of duplicate links observed for step $i$
- $k$ = smoothing constant (for example $k=6$)

Purpose:

- Low-link steps can be noisy, so $S_i$ shrinks their score down.
- As evidence grows ($n_i$ increases), $S_i\to 1$.

## Intuition summary

- $d$ measures closeness of duplicate occurrences.
- $W$ sets the boundary for how far still counts as concerning proximity.
- $S_i$ controls confidence so sparse evidence does not dominate rankings.

## Tiny worked example

Assume $W=10$, duplicate distances for one step are $d=\{1,2,8,15\}$.

Raw proximity terms become:

$$
\left\{1-\frac{1}{10},1-\frac{2}{10},1-\frac{8}{10},\max\left(0,1-\frac{15}{10}\right)\right\}=\{0.9,0.8,0.2,0\}
$$

Mean raw penalty = $0.475$.

If $n_i=4$ and $k=6$, then:

$$
S_i=\frac{4}{10}=0.4
$$

So:

$$
A_i=0.4\times 0.475=0.19
$$

This shows how shrinkage keeps low-evidence steps from looking overly extreme.
