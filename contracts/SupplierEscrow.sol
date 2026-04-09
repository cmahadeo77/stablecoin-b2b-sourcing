// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * SupplierEscrow.sol
 *
 * Escrow contract for B2B ingredient sourcing payments.
 * Buyer deposits USDC, funds release to supplier upon
 * delivery confirmation from an authorized oracle.
 *
 * Use case: Personal care brands paying international ingredient suppliers —
 * shea butter, argan oil, botanical extracts, fragrance compounds.
 *
 * Author: Arikina — hello@arikina.com
 */

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract SupplierEscrow {

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    address public immutable buyer;
    address public immutable supplier;
    address public immutable oracle;       // logistics/delivery confirmation oracle
    IERC20  public immutable usdc;

    string  public ingredientDescription;
    string  public poNumber;
    uint256 public amount;                 // USDC (6 decimals)

    enum State { AWAITING_DEPOSIT, FUNDED, SHIPPED, RELEASED, REFUNDED, DISPUTED }
    State public state;

    uint256 public fundedAt;
    uint256 public deliveryDeadline;       // unix timestamp
    string  public trackingId;

    // -----------------------------------------------------------------------
    // Events
    // -----------------------------------------------------------------------

    event Funded(uint256 amount, uint256 deadline);
    event ShipmentConfirmed(string trackingId);
    event PaymentReleased(address supplier, uint256 amount);
    event Refunded(address buyer, uint256 amount);
    event Disputed(string reason);

    // -----------------------------------------------------------------------
    // Modifiers
    // -----------------------------------------------------------------------

    modifier onlyBuyer()   { require(msg.sender == buyer,    "Not buyer");   _; }
    modifier onlyOracle()  { require(msg.sender == oracle,   "Not oracle");  _; }
    modifier inState(State _state) {
        require(state == _state, "Invalid state transition");
        _;
    }

    // -----------------------------------------------------------------------
    // Constructor
    // -----------------------------------------------------------------------

    constructor(
        address _supplier,
        address _oracle,
        address _usdc,
        string memory _poNumber,
        string memory _ingredientDescription,
        uint256 _amount,
        uint256 _deliveryDays
    ) {
        buyer               = msg.sender;
        supplier            = _supplier;
        oracle              = _oracle;
        usdc                = IERC20(_usdc);
        poNumber            = _poNumber;
        ingredientDescription = _ingredientDescription;
        amount              = _amount;
        deliveryDeadline    = block.timestamp + (_deliveryDays * 1 days);
        state               = State.AWAITING_DEPOSIT;
    }

    // -----------------------------------------------------------------------
    // Buyer actions
    // -----------------------------------------------------------------------

    /**
     * Buyer deposits USDC into escrow to activate the purchase order.
     * Supplier can see the deposit on-chain — trust established before shipment.
     */
    function deposit() external onlyBuyer inState(State.AWAITING_DEPOSIT) {
        require(
            usdc.transferFrom(msg.sender, address(this), amount),
            "USDC transfer failed"
        );
        state = State.FUNDED;
        fundedAt = block.timestamp;
        emit Funded(amount, deliveryDeadline);
    }

    /**
     * Buyer can request refund if delivery deadline passes with no confirmation.
     */
    function requestRefund() external onlyBuyer {
        require(
            state == State.FUNDED || state == State.SHIPPED,
            "Cannot refund in current state"
        );
        require(block.timestamp > deliveryDeadline, "Delivery deadline not passed");
        _refund();
    }

    /**
     * Buyer can raise a dispute (e.g., wrong goods, quality issue).
     */
    function dispute(string calldata reason) external onlyBuyer inState(State.SHIPPED) {
        state = State.DISPUTED;
        emit Disputed(reason);
    }

    // -----------------------------------------------------------------------
    // Oracle actions (logistics / delivery confirmation)
    // -----------------------------------------------------------------------

    /**
     * Oracle confirms shipment has been dispatched with tracking ID.
     */
    function confirmShipment(string calldata _trackingId)
        external
        onlyOracle
        inState(State.FUNDED)
    {
        trackingId = _trackingId;
        state = State.SHIPPED;
        emit ShipmentConfirmed(_trackingId);
    }

    /**
     * Oracle confirms delivery — automatically releases USDC to supplier.
     */
    function confirmDelivery() external onlyOracle inState(State.SHIPPED) {
        _release();
    }

    /**
     * Oracle resolves dispute in supplier's favor (e.g., goods were correct).
     */
    function resolveDisputeInFavorOfSupplier() external onlyOracle inState(State.DISPUTED) {
        _release();
    }

    /**
     * Oracle resolves dispute in buyer's favor (e.g., goods were wrong).
     */
    function resolveDisputeInFavorOfBuyer() external onlyOracle inState(State.DISPUTED) {
        _refund();
    }

    // -----------------------------------------------------------------------
    // Internal
    // -----------------------------------------------------------------------

    function _release() internal {
        state = State.RELEASED;
        uint256 balance = usdc.balanceOf(address(this));
        require(usdc.transfer(supplier, balance), "Transfer to supplier failed");
        emit PaymentReleased(supplier, balance);
    }

    function _refund() internal {
        state = State.REFUNDED;
        uint256 balance = usdc.balanceOf(address(this));
        require(usdc.transfer(buyer, balance), "Refund to buyer failed");
        emit Refunded(buyer, balance);
    }

    // -----------------------------------------------------------------------
    // View
    // -----------------------------------------------------------------------

    function escrowDetails() external view returns (
        string memory _poNumber,
        string memory _ingredient,
        uint256 _amount,
        State _state,
        uint256 _deadline,
        string memory _tracking
    ) {
        return (poNumber, ingredientDescription, amount, state, deliveryDeadline, trackingId);
    }

    function isOverdue() external view returns (bool) {
        return (state == State.FUNDED || state == State.SHIPPED)
            && block.timestamp > deliveryDeadline;
    }
}
