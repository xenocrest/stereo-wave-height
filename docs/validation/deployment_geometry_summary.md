# Deployment geometry summary

The current evidence consists of two one-dimensional slices, not a complete map of $(B,Z)\in\Omega_{valid}$.

| slice | case | B | Z | nominal disparity | sensitivity | result |
|---|---|---:|---:|---:|---:|---|
| distance | D1 | 0.20 m | 1.75 m | 265.010 px | 6.604 mm/px | FAIL raw support |
| distance | D0 | 0.20 m | 2.00 m | 231.884 px | 8.625 mm/px | PASS |
| distance | D2 | 0.20 m | 2.50 m | 185.507 px | 13.477 mm/px | BLOCKED plane fit |
| baseline | B1 | 0.15 m | 2.00 m | 173.913 px | 11.500 mm/px | PASS |
| baseline | B0 | 0.20 m | 2.00 m | 231.884 px | 8.625 mm/px | PASS |
| baseline | B2 | 0.25 m | 2.00 m | 289.855 px | 6.900 mm/px | PASS |

The governing relations are $d=f_{px}B/Z$ and $|\partial Z/\partial d|=Z^2/(f_{px}B)$. Larger B or smaller Z improves ideal depth sensitivity but raises disparity and reduces common field of view. Only the listed combinations have end-to-end evidence. A future `(0.25 m,2.50 m)` cross-check is mathematically motivated but not yet authorized or tested.
