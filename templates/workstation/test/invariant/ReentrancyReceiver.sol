// SPDX-License-Identifier: MIT
pragma solidity 0.8.38;

/// @title ReentrancyReceiver — spec Stage 10: cross-contract reentrancy-set
///        handlers simulating malicious token and receiver hooks.
///        Deploy and hand its address to the target wherever the target calls
///        out (ERC777-style tokens, ERC721/1155 receivers, pair callbacks).
contract ReentrancyReceiver {
    enum Mode { NONE, REENTER, REVERT, GRIEF }

    address public target;
    bytes4 public reenterSelector;
    Mode public mode = Mode.REENTER;
    uint256 public reentryBudget = 3; // bounded re-entry depth

    event Reentered(bytes data, uint256 remaining);

    function arm(address target_, bytes4 selector_, Mode mode_) external {
        target = target_;
        reenterSelector = selector_;
        mode = mode_;
    }

    // --- hooks the target may call into ---

    receive() external payable {
        _act();
    }

    fallback() external payable {
        _act();
    }

    function tokensReceived(address, address, address, uint256, bytes calldata, bytes calldata) external {
        _act();
    }

    function onERC721Received(address, address, uint256, bytes calldata) external returns (bytes4) {
        _act();
        return this.onERC721Received.selector;
    }

    function onERC1155Received(address, address, uint256, uint256, bytes calldata) external returns (bytes4) {
        _act();
        return this.onERC1155Received.selector;
    }

    function uniswapV3SwapCallback(int256, int256, bytes calldata) external {
        _act();
    }

    function flashLoanReceiver(address, address, uint256, uint256, bytes calldata) external returns (bytes32) {
        _act();
        return keccak256("ERC3156FlashBorrower.onFlashLoan");
    }

    function _act() internal {
        emit ReentrancyReceiver.msg_data(msg.data, reentryBudget);
        if (mode == Mode.REVERT) {
            revert("HACVSP: malicious revert");
        }
        if (mode == Mode.REENTER && reentryBudget > 0 && target != address(0)) {
            reentryBudget -= 1;
            (bool ok, ) = target.call(abi.encodeWithSelector(reenterSelector));
            ok; // outcome recorded by the invariant suite
        }
        if (mode == Mode.GRIEF) {
            // consume gas to grief the target mid-callback
            for (uint256 i = 0; i < 50_000; i++) {
                assembly { pop(i) }
            }
        }
    }

    // tiny event-name shim so the emit above compiles without imports
    event msg_data(bytes, uint256);
}
