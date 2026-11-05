// SPDX-License-Identifier: MIT
pragma solidity 0.8.38;

import {Actors} from "./Actors.sol";
import {ReentrancyReceiver} from "./ReentrancyReceiver.sol";

/// @title Handler — spec Stage 10 handler architecture.
/// Ghost variable state trackers mirror target accounting so invariants can
/// prove conservation of capital and solvency across call sequences.
///
/// OPERATOR: wire every public/external state-changing function of the target
/// as a handler that (1) bounds inputs, (2) calls as a ghost actor, and
/// (3) updates the ghost trackers. Handler functions must never revert for
/// reasons other than target-enforced invariants (fail_on_revert=false).
contract Handler is Actors {
    address public immutable TARGET;
    ReentrancyReceiver public immutable REENTRANT;

    // ---- ghost trackers (mirror the target's accounting) ----
    uint256 public ghost_totalDeposited;
    uint256 public ghost_totalWithdrawn;
    uint256 public ghost_supplyDelta;

    constructor(address target) {
        TARGET = target;
        REENTRANT = new ReentrancyReceiver();
        REENTRANT.arm(target, bytes4(0), ReentrancyReceiver.Mode.REENTER);
    }

    // ---- handler examples (OPERATOR: adapt to the target) ----

    // function deposit(uint256 actorSeed, uint256 amount) external {
    //     amount = bound(amount, 0, address(this).balance);
    //     address a = actor(actorSeed);
    //     vm.startPrank(a);
    //     TARGET.deposit{value: amount}();
    //     vm.stopPrank();
    //     ghost_totalDeposited += amount;
    // }

    // function withdraw(uint256 actorSeed, uint256 amount) external {
    //     address a = actor(actorSeed);
    //     vm.startPrank(a);
    //     TARGET.withdraw(amount);
    //     vm.stopPrank();
    //     ghost_totalWithdrawn += amount;
    // }

    // function armReentrancy(bytes4 selector) external {
    //     REENTRANT.arm(TARGET, selector, ReentrancyReceiver.Mode.REENTER);
    // }

    // function setReentrancyMode(uint8 m) external {
    //     REENTRANT.arm(TARGET, REENTRANT.reenterSelector(), ReentrancyReceiver.Mode(m));
    // }

    // ---- ghost-derived conservation getters (used by invariants) ----
    function netFlow() external view returns (int256) {
        return int256(ghost_totalDeposited) - int256(ghost_totalWithdrawn);
    }
}
