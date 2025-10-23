"""
Recurring transfer strategy.
"""

from __future__ import annotations

import numpy as np
from decimal import Decimal

from finbricklab.core.bricks import TBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.events import Event
from finbricklab.core.interfaces import ITransferStrategy
from finbricklab.core.results import BrickOutput
from finbricklab.core.currency import create_amount


class TransferRecurring(ITransferStrategy):
    """
    Recurring transfer strategy (kind: 't.transfer.recurring').

    This strategy models periodic transfers between internal accounts
    that occur at regular intervals. The transfers move money from one
    internal account to another without affecting net worth.

    Required Parameters:
        - amount: The amount to transfer each period
        - frequency: Transfer frequency ('MONTHLY', 'QUARTERLY', 'YEARLY')
        - currency: Currency code (default: 'EUR')

    Required Links:
        - from: Source account ID
        - to: Destination account ID

    Optional Parameters:
        - start_date: When to start transfers (default: scenario start)
        - end_date: When to stop transfers (default: scenario end)
        - day_of_month: Day of month for transfers (default: 1)
        - fees: Transfer fees (amount and account)
        - priority: Transfer priority for same-day ordering (default: 0)

    Note:
        This strategy generates recurring transfer events at the specified frequency.
        The actual account balance changes are handled by the journal system.
    """

    def prepare(self, brick: TBrick, ctx: ScenarioContext) -> None:
        """
        Prepare the recurring transfer strategy.

        Validates that required parameters and links are present.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Raises:
            AssertionError: If required parameters are missing
        """
        # Validate required parameters
        assert "amount" in brick.spec, "Missing required parameter: amount"
        assert "frequency" in brick.spec, "Missing required parameter: frequency"
        
        # Validate required links
        assert brick.links is not None, "Missing required links"
        assert "from" in brick.links, "Missing required link: from"
        assert "to" in brick.links, "Missing required link: to"
        
        # Validate amount is positive
        amount = brick.spec["amount"]
        if isinstance(amount, (int, float)):
            amount = Decimal(str(amount))
        assert amount > 0, "Transfer amount must be positive"
        
        # Validate frequency
        frequency = brick.spec["frequency"]
        valid_frequencies = ["MONTHLY", "QUARTERLY", "YEARLY"]
        assert frequency in valid_frequencies, f"Frequency must be one of {valid_frequencies}"
        
        # Validate accounts are different
        from_account = brick.links["from"]
        to_account = brick.links["to"]
        assert from_account != to_account, "Source and destination accounts must be different"
        
        # Validate optional parameters
        if "fees" in brick.spec:
            fees = brick.spec["fees"]
            assert "amount" in fees, "Fee amount is required"
            assert "account" in fees, "Fee account is required"

    def simulate(self, brick: TBrick, ctx: ScenarioContext) -> BrickOutput:
        """
        Simulate the recurring transfer.

        Generates transfer events at the specified frequency.

        Args:
            brick: The transfer brick
            ctx: The simulation context

        Returns:
            BrickOutput with recurring transfer events and zero cash flows
        """
        T = len(ctx.t_index)
        
        # Get transfer parameters
        amount = Decimal(str(brick.spec["amount"]))
        frequency = brick.spec["frequency"]
        currency = brick.spec.get("currency", "EUR")
        day_of_month = brick.spec.get("day_of_month", 1)
        priority = brick.spec.get("priority", 0)
        
        # Create amount object
        amount_obj = create_amount(amount, currency)
        
        # Determine transfer frequency in months
        if frequency == "MONTHLY":
            interval_months = 1
        elif frequency == "QUARTERLY":
            interval_months = 3
        elif frequency == "YEARLY":
            interval_months = 12
        else:
            raise ValueError(f"Invalid frequency: {frequency}")
        
        # Generate transfer events
        events = []
        current_date = brick.start_date if brick.start_date else ctx.t_index[0]
        end_date = brick.spec.get("end_date")
        
        while current_date <= ctx.t_index[-1]:
            if end_date and current_date > end_date:
                break
            
            # Create transfer event
            event = Event(
                current_date,
                "transfer",
                f"Recurring transfer: {amount_obj}",
                {
                    "amount": float(amount),
                    "currency": currency,
                    "from": brick.links["from"],
                    "to": brick.links["to"],
                    "frequency": frequency,
                    "priority": priority
                }
            )
            events.append(event)
            
            # Add fee event if specified
            if "fees" in brick.spec:
                fees = brick.spec["fees"]
                fee_amount = Decimal(str(fees["amount"]))
                fee_currency = fees.get("currency", currency)
                fee_amount_obj = create_amount(fee_amount, fee_currency)
                
                fee_event = Event(
                    current_date,
                    "transfer_fee",
                    f"Transfer fee: {fee_amount_obj}",
                    {
                        "amount": float(fee_amount),
                        "currency": fee_currency,
                        "account": fees["account"],
                        "priority": priority + 1
                    }
                )
                events.append(fee_event)
            
            # Move to next transfer date
            if frequency == "MONTHLY":
                # Add one month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            elif frequency == "QUARTERLY":
                # Add three months
                if current_date.month <= 9:
                    current_date = current_date.replace(month=current_date.month + 3)
                else:
                    current_date = current_date.replace(year=current_date.year + 1, month=current_date.month + 3 - 12)
            elif frequency == "YEARLY":
                # Add one year
                current_date = current_date.replace(year=current_date.year + 1)
        
        return BrickOutput(
            cash_in=np.zeros(T),
            cash_out=np.zeros(T),
            asset_value=np.zeros(T),
            debt_balance=np.zeros(T),
            events=events
        )
