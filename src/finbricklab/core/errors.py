"""
Error classes for FinBrickLab.

This module defines custom exception classes used throughout the FinBrickLab system
for handling configuration errors, validation failures, and other runtime issues.
"""


class ConfigError(Exception):
    """
    Configuration error during scenario setup or validation.

    This exception is raised when there are issues with brick configuration,
    invalid parameters, missing required fields, or structural problems in scenarios.

    **Common Causes:**
    - Missing required parameters in brick specifications
    - Invalid parameter values (negative amounts, invalid dates)
    - Circular dependencies between bricks
    - Missing referenced brick IDs in links
    - Invalid cash routing configurations

    **Example Usage:**
        ```python
        from finbricklab.core.errors import ConfigError
        from finbricklab.core.bricks import ABrick

        try:
            # This will raise ConfigError if initial_balance is missing
            cash = ABrick(
                id="cash",
                name="Savings",
                kind="a.cash",
                spec={}  # Missing required initial_balance
            )
        except ConfigError as e:
            print(f"Configuration error: {e}")

        # Custom usage in strategies
        def validate_spec(spec):
            if "amount_monthly" not in spec:
                raise ConfigError("amount_monthly is required for income flows")
            if spec["amount_monthly"] <= 0:
                raise ConfigError("amount_monthly must be positive")
        ```

    **When to Use:**
    - In strategy prepare() methods for parameter validation
    - During scenario validation and setup
    - When validating brick specifications
    - For cash routing and dependency validation
    """

    pass
