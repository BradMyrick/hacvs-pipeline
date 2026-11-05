// SPDX-License-Identifier: MIT
pragma solidity 0.8.38;

import {Test} from "forge-std/Test.sol";
import {Counter} from "src/Counter.sol";

contract CounterTest is Test {
    Counter c;

    function setUp() public {
        c = new Counter();
    }

    function test_increment() public {
        c.increment();
        assertEq(c.number(), 1);
    }

    function testFuzz_setNumber(uint256 x) public {
        c.setNumber(x);
        assertEq(c.number(), x);
    }

    function test_unprivileged_cannot_set() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert(Counter.Unauthorized.selector);
        c.setNumber(42);
    }
}
