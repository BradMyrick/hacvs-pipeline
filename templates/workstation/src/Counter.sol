// SPDX-License-Identifier: MIT
pragma solidity >=0.8.28 <0.9.0;

/// @notice Minimal example target so the scaffold builds out of the box.
///         Replace with the real protocol sources.
contract Counter {
    uint256 public number;
    event NumberSet(uint256 indexed oldNumber, uint256 newNumber);

    error Unauthorized();

    address public owner;

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function setNumber(uint256 newNumber) external onlyOwner {
        uint256 old = number;
        number = newNumber;
        emit NumberSet(old, newNumber);
    }

    function increment() external {
        uint256 old = number;
        number = number + 1;
        emit NumberSet(old, number);
    }
}
