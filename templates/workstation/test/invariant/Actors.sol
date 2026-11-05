// SPDX-License-Identifier: MIT
pragma solidity 0.8.38;

import {Test} from "forge-std/Test.sol";
import {console2} from "forge-std/console2.sol";

/// @title Actors — spec Stage 10 handler architecture: ghost accounts
///        separating admin vs non-privileged users.
contract Actors {
    address public immutable ADMIN = makeAddr("hacvsp:admin");
    address public immutable USER_1 = makeAddr("hacvsp:user1");
    address public immutable USER_2 = makeAddr("hacvsp:user2");
    address public immutable ATTACKER = makeAddr("hacvsp:attacker");
    address[] public unprivileged;

    constructor() {
        unprivileged.push(USER_1);
        unprivileged.push(USER_2);
        unprivileged.push(ATTACKER);
    }

    function randomUnprivileged(uint256 seed) public view returns (address) {
        return unprivileged[seed % unprivileged.length];
    }

    /// Iterate actors: 0=ADMIN, 1..N = unprivileged set.
    function actor(uint256 i) public view returns (address) {
        if (i == 0) return ADMIN;
        return unprivileged[(i - 1) % unprivileged.length];
    }

    function actorCount() public view returns (uint256) {
        return 1 + unprivileged.length;
    }

    function makeAddr(string memory name) internal pure returns (address) {
        // deterministic, non-cheatcode address derivation (works under echidna/medusa)
        return address(uint160(uint256(keccak256(abi.encodePacked("hacvsp:actor:", name)))));
    }
}
