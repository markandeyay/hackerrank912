"""Scratch: integer-nominal decompositions of request_06's reference variable reserve (235 = 539.10 - rent 254.10 - subs 50).
Well-supported nominals fixed: G=45 (n=18, mean 45.08), T=27 (n=35, 26.98), D in {45,46} (n=25, 45.88), E=35 (n=5, 35.01).
Utilities (n=5: 51.86..58.98) and shopping (n=5: 37.96..46.25) are the free variables; print the U+Sh each subset needs."""
import itertools
for kT, kD, kE, hasU, hasG, hasSh in itertools.product([1, 2, 3], [0, 1, 2], [0, 1], [0, 1], [0, 1], [0, 1]):
    for D in (45, 46):
        fixed_part = kT * 27 + kD * D + kE * 35 + hasG * 45
        need = 235 - fixed_part  # = hasU*U + hasSh*Sh
        ok = False
        if hasU and hasSh:
            ok = 2 * 45 <= need <= 60 + 47
        elif hasU:
            ok = 48 <= need <= 62
        elif hasSh:
            ok = 36 <= need <= 47
        else:
            ok = need == 0
        if ok:
            print(f"T x{kT} D x{kD}(={D}) E x{kE} U={bool(hasU)} G={bool(hasG)} Sh={bool(hasSh)} -> U+Sh (or single) must be {need}  [means: U 55.70, Sh 41.00, U+Sh 96.70]")
