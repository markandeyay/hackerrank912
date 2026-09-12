"""Scratch trace for request_17: decompose the reference reserve 140,430 and the
post-payday window 03-15..04-13. Does not touch the engine."""
import statistics, itertools
G=[9392.54,7679.25,10039.54,9785.51,7187.32,8574.98,11380.46,6706.54,7585.37,7446.25,10300.07,8500.09,7237.45,8836.99,10690,10432.03,11392.07,8124.44,11433.33,7093.83,8638.54,8581.99,11342.57,10873.47,8543.01,8716.51]
T=[3913.59,6046.8,3972.38,5639.47,4445.42,6225.69,5386.34,5421.55,5936.87,6420.35,4008.13,5126.25,5036.82,6170.7,5790.36,4328.91,5080.56,4844.94,5940.36,6406.38,5758.89,4661.7,5650.43,3902.91,5741.08,5372.15]
D=[5641.06,4425.44,4695.55,5554.91,6027.54,5593.53,6839.37,6048.91,6795.26,6797.26,5254.41,6688.81,4747.76]
U=[9481.13,9530.77,10246.53,9948.15,8487.15]
bal, mn, req, sal = 550379.58, 166100.0, 274600.0, 206000.0
fixed = 49600+13660+30200+2055+1675  # rent, education, debt, music, delivery
print("fixed pre-payday (03-02..03-13):", fixed)
for name, h in (("groceries",G),("transport",T),("dining",D),("utilities",U)):
    print(f"{name:10s} n={len(h):2d} mean={statistics.mean(h):9.2f} median={statistics.median(h):9.2f} min={min(h):9.2f} max={max(h):9.2f} midrange={(min(h)+max(h))/2:9.2f} max/min={max(h)/min(h):.3f}")
mG,mT,mD,mU = map(statistics.mean,(G,T,D,U))
ours_pre_var = mU + 2*mG + 2*mT + mD
ref_var = 140430 - fixed
print(f"\nOur pre-payday variable total = U + 2G + 2T + D = {ours_pre_var:.2f}; our reserve = {fixed+ours_pre_var:.2f}")
print(f"Reference reserve 140430 -> variable part = {ref_var}; ratio ref/ours = {ref_var/ours_pre_var:.5f}")
# post window 03-15..04-13: fixed again + U + 4G + 4T + 2D
ours_post = fixed + mU + 4*mG + 4*mT + 2*mD
bal_0314_ours = bal - fixed - ours_pre_var
margin_ours = bal_0314_ours + sal - req - mn
print(f"\nOurs: bal 03-14 = {bal_0314_ours:.2f}; after salary+payment on 03-15 = {bal_0314_ours+sal-req:.2f}; room above min for 03-15..04-13 = {margin_ours:.2f}")
print(f"Ours: projected debits 03-15..04-13 = fixed {fixed} + U {mU:.2f} + 4G {4*mG:.2f} + 4T {4*mT:.2f} + 2D {2*mD:.2f} = {ours_post:.2f}; shortfall = {ours_post-margin_ours:.2f}")
bal_0314_ref = bal - 140430
margin_ref = bal_0314_ref + sal - req - mn
print(f"\nRef: bal 03-14 = {bal_0314_ref:.2f}; after salary+payment = {bal_0314_ref+sal-req:.2f}; room = {margin_ref:.2f}")
print(f"Ref post-window with same counts = fixed + U + 4G + 4T + 2D = fixed + 43240 + (43240 - U) = {fixed + 2*ref_var} - U; passes iff U >= {fixed + 2*ref_var - margin_ref:.2f}")
# enumerate plausible nominals: uniform +-30% bounds => nominal in [max/1.3, min/0.7]; grid step 10
def rng(h, a=0.30):
    lo, hi = max(h)/(1+a), min(h)/(1-a)
    return range(int(lo//10*10), int(hi//10*10)+10, 10)
sols=[]
for u in rng(U,0.20):
    for g in rng(G):
        for t in rng(T):
            d = 43240 - u - 2*g - 2*t
            if d % 10 == 0 and d in rng(D):
                post = fixed + u + 4*g + 4*t + 2*d
                sols.append((u,g,t,d, margin_ref-post))
print(f"\n{len(sols)} grid decompositions (step 10, nominal within +-30% band of history; utilities +-20%)")
if sols:
    ms=[s[4] for s in sols]
    print(f"post-window pass margin over all decompositions: min={min(ms):.2f} max={max(ms):.2f}  (all pass: {min(ms)>0})")
    for s in sols[::max(1,len(sols)//8)]:
        print("  U=%d G=%d T=%d D=%d -> 03-15 payment margin %.2f" % s)
# alternative occurrence counts pre-payday
print("\nAlternative pre-payday counts (kG groceries, kT transport, kD dining) -> implied U with G,T,D at midrange:")
midG,midT,midD=(min(G)+max(G))/2,(min(T)+max(T))/2,(min(D)+max(D))/2
for kG,kT,kD in itertools.product((1,2,3),(1,2,3),(0,1,2)):
    u = 43240 - kG*midG - kT*midT - kD*midD
    flag = "plausible" if min(U)/1.3 <= u <= max(U)*1.3 else "-"
    if flag=="plausible" or (kG,kT,kD)==(2,2,1): print(f"  {kG},{kT},{kD}: U={u:9.2f} {flag}")
# post-window with fewer weekly occurrences (3G,3T) using our means -> margin
print(f"\nOurs with 3 groceries + 3 transport in post window: debits = {fixed+mU+3*mG+3*mT+2*mD:.2f} vs room {margin_ours:.2f}")
