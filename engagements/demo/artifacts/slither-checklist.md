'forge clean' running (wd: /engagement/target)
'forge config --json' running
'forge build --build-info --deny never --skip ./test/** ./script/** --force' running (wd: /engagement/target)
**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [solc-version](#solc-version) (1 results) (Informational)
 - [immutable-states](#immutable-states) (1 results) (Optimization)
## solc-version
Impact: Informational
Confidence: High
 - [ ] ID-0
Version constraint >=0.8.28<0.9.0 is too complex.
It is used by:
	- [>=0.8.28<0.9.0](src/Counter.sol#L2)

src/Counter.sol#L2


## immutable-states
Impact: Optimization
Confidence: High
 - [ ] ID-1
[Counter.owner](src/Counter.sol#L12) should be immutable 

src/Counter.sol#L12


