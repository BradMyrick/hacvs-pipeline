'forge clean' running (wd: /engagement/target)
'forge config --json' running
'forge build --build-info --deny never --skip ./test/** ./script/** --force' running (wd: /engagement/target)
**THIS CHECKLIST IS NOT COMPLETE**. Use `--show-ignored-findings` to show all the results.
Summary
 - [immutable-states](#immutable-states) (1 results) (Optimization)
## immutable-states
Impact: Optimization
Confidence: High
 - [ ] ID-0
[Counter.owner](src/Counter.sol#L12) should be immutable 

src/Counter.sol#L12


