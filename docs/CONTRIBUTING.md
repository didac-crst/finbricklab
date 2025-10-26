# Contributing to FinBrickLab

Thank you for your interest in contributing to FinBrickLab! This guide will help you get started with development and contributing to the project.

## Table of Contents

* [Development Setup](#development-setup)
* [Project Structure](#project-structure)
* [Adding New Strategies](#adding-new-strategies)
* [Adding New Charts](#adding-new-charts-section)
* [Testing Guidelines](#testing-guidelines)
* [Code Style](#code-style)
* [Pull Request Process](#pull-request-process)

---

## Development Setup

### Prerequisites

- Python 3.9+
- Poetry (for dependency management)
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/your-org/finbricklab.git
cd finbricklab

# Install dependencies
poetry install

# Install with visualization extras
poetry install --extras viz

# Install pre-commit hooks
poetry run pre-commit install

# Run tests to verify setup
poetry run pytest
```

### Development Environment

```bash
# Activate virtual environment
poetry shell

# Run tests with coverage
poetry run pytest --cov=finbricklab

# Run linting
poetry run ruff check .
poetry run black --check .

# Run type checking
poetry run mypy src/
```

---

## Project Structure

```
finbricklab/
├── src/finbricklab/           # Main package
│   ├── core/                  # Core classes and interfaces
│   │   ├── bricks.py         # FinBrick classes
│   │   ├── entity.py         # Entity system
│   │   ├── scenario.py       # Scenario orchestrator
│   │   ├── interfaces.py     # Strategy interfaces
│   │   ├── registry.py       # Strategy registry
│   │   └── ...
│   ├── strategies/            # Strategy implementations
│   │   ├── flow/             # Flow strategies
│   │   ├── schedule/         # Schedule strategies
│   │   └── valuation/        # Valuation strategies
│   ├── charts.py             # Visualization functions
│   ├── kpi.py               # KPI calculation utilities
│   ├── fx.py                # Foreign exchange utilities
│   └── __init__.py          # Package exports
├── tests/                     # Test suite
│   ├── core/                 # Core functionality tests
│   ├── strategies/           # Strategy tests
│   └── ...
├── docs/                      # Documentation
├── examples/                  # Example scripts
└── scripts/                   # Utility scripts
```

---

## Adding New Strategies

### 1. Implement Strategy Interface

Create a new strategy class implementing the appropriate interface:

```python
# src/finbricklab/strategies/valuation/my_strategy.py
from finbricklab.core.interfaces import IValuationStrategy
from finbricklab.core.context import ScenarioContext

class MyAssetStrategy(IValuationStrategy):
    """Custom asset strategy."""

    def value(self, context: ScenarioContext, spec: dict) -> float:
        """Calculate current value."""
        # Implementation here
        return calculated_value
```

### 2. Register Strategy

Add to the appropriate registry:

```python
# src/finbricklab/strategies/__init__.py
from .valuation.my_strategy import MyAssetStrategy
from finbricklab.core.registry import ValuationRegistry

# Register the strategy
ValuationRegistry.register("a.my_asset", MyAssetStrategy())
```

### 3. Add Tests

Create comprehensive tests:

```python
# tests/strategies/test_my_strategy.py
import pytest
from finbricklab.strategies.valuation.my_strategy import MyAssetStrategy

class TestMyAssetStrategy:
    def test_basic_valuation(self):
        """Test basic valuation logic."""
        strategy = MyAssetStrategy()
        context = create_test_context()
        spec = {"param1": 1000.0, "param2": 0.05}

        result = strategy.value(context, spec)

        assert result > 0
        assert abs(result - expected_value) < 0.01

    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        # Test zero values, negative values, etc.
        pass

    def test_integration(self):
        """Test integration with scenario engine."""
        # Test that the strategy works in a full scenario
        pass
```

### 4. Update Documentation

Add to the strategy catalog:

```markdown
# docs/STRATEGIES.md

## a.my_asset

**Purpose**: Description of what this strategy does.

**Specification**:
```json
{
  "param1": 1000.0,
  "param2": 0.05
}
```

**Parameters**:
- `param1` (float): Description of parameter
- `param2` (float): Description of parameter

**Example**:
```python
asset = ABrick(
    id="my_asset",
    name="My Asset",
    kind="a.my_asset",
    spec={"param1": 1000.0, "param2": 0.05}
)
```
```

---

## Adding New Charts {#adding-new-charts-section}

### 1. Implement Chart Function

Create a new chart function in `charts.py`:

```python
def my_new_chart(
    tidy: pd.DataFrame,
    scenario_name: str | None = None
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Description of what this chart shows.

    Args:
        tidy: DataFrame from Entity.compare()
        scenario_name: Name of scenario to analyze

    Returns:
        Tuple of (plotly_figure, tidy_dataframe_used)
    """
    _check_plotly()

    # Chart implementation
    fig = go.Figure()
    # ... add traces, layout, etc.

    return fig, tidy
```

### 2. Add to Exports

Update `__init__.py` to export the new chart:

```python
# src/finbricklab/__init__.py
try:
    from .charts import (
        # ... existing charts
        my_new_chart,
    )
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False

# Add to __all__ if charts available
if CHARTS_AVAILABLE:
    __all__.extend([
        # ... existing charts
        "my_new_chart",
    ])
```

### 3. Add Tests

Create chart tests:

```python
# tests/test_charts.py
def test_my_new_chart(self, sample_tidy_data):
    """Test my new chart function."""
    try:
        fig, data = my_new_chart(sample_tidy_data)

        assert fig is not None
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0

    except ImportError:
        pytest.skip("Plotly not available")
```

### 4. Update Documentation

Add to API reference and examples:

- docs/API_REFERENCE.md
````markdown
### my_new_chart

```python
def my_new_chart(tidy: pd.DataFrame, scenario_name: str = None) -> tuple[go.Figure, pd.DataFrame]:
    """Description of chart functionality."""
```
````

- docs/EXAMPLES.md
````markdown
## My New Chart Example
```python
from finbricklab import my_new_chart

fig, data = my_new_chart(comparison_df)
fig.show()
```
````

---

## Adding New KPI Functions

### 1. Implement KPI Function

Add to `kpi.py`:

```python
def my_kpi(
    df: pd.DataFrame,
    param1_col: str = "param1",
    param2_col: str = "param2",
) -> pd.Series:
    """
    Calculate my custom KPI.

    Args:
        df: DataFrame with canonical schema
        param1_col: Column name for parameter 1
        param2_col: Column name for parameter 2

    Returns:
        Series with KPI values
    """
    # Implementation
    result = df[param1_col] / df[param2_col]
    return pd.Series(result, index=df.index, name="my_kpi")
```

### 2. Add Tests

```python
# tests/test_kpi_utilities.py
def test_my_kpi(self, sample_df):
    """Test my KPI calculation."""
    kpi_result = my_kpi(sample_df)

    assert len(kpi_result) == len(sample_df)
    assert kpi_result.name == "my_kpi"
    assert not kpi_result.isna().any()
```

### 3. Update Documentation

Add to API reference and examples.

---

## Testing Guidelines

### Test Structure

Follow the existing test patterns:

```python
class TestMyFeature:
    """Test suite for my feature."""

    @pytest.fixture
    def sample_data(self):
        """Create sample data for testing."""
        return create_test_data()

    def test_basic_functionality(self, sample_data):
        """Test basic functionality."""
        # Test the happy path
        pass

    def test_edge_cases(self, sample_data):
        """Test edge cases."""
        # Test boundary conditions
        pass

    def test_error_conditions(self, sample_data):
        """Test error handling."""
        # Test invalid inputs, missing data, etc.
        pass

    def test_integration(self, sample_data):
        """Test integration with other components."""
        # Test that everything works together
        pass
```

### Test Data

Use the golden dataset for regression testing:

```python
def test_with_golden_dataset(self):
    """Test using the golden dataset."""
    golden_path = Path(__file__).parent / "data" / "golden_12m.csv"
    df = pd.read_csv(golden_path)

    result = my_function(df)

    # Verify against known values
    assert result.iloc[5] == expected_value
```

### Coverage

Aim for high test coverage:

```bash
# Run with coverage
poetry run pytest --cov=finbricklab --cov-report=html

# Check coverage
poetry run pytest --cov=finbricklab --cov-fail-under=90
```

---

## Code Style

### Python Style

Follow PEP 8 and use the configured tools:

```bash
# Format code
poetry run black src/ tests/

# Check style
poetry run ruff check src/ tests/

# Fix auto-fixable issues
poetry run ruff check --fix src/ tests/
```

### Type Hints

Use type hints for all function signatures:

```python
from typing import Optional, List, Dict, Tuple
import pandas as pd

def my_function(
    df: pd.DataFrame,
    param: Optional[str] = None,
) -> Tuple[pd.Series, Dict[str, float]]:
    """Function with proper type hints."""
    pass
```

### Docstrings

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int) -> float:
    """
    Brief description of what the function does.

    Longer description if needed, explaining the purpose,
    algorithm, or any important details.

    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2

    Returns:
        Description of return value

    Raises:
        ValueError: When invalid input is provided

    Example:
        >>> result = my_function("test", 42)
        >>> print(result)
        3.14
    """
    pass
```

### Naming Conventions

- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

---

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
   ```bash
   poetry run pytest
   ```

2. **Check Style**: Fix any linting issues
   ```bash
   poetry run ruff check src/ tests/
   poetry run black --check src/ tests/
   ```

3. **Type Check**: Ensure type hints are correct
   ```bash
   poetry run mypy src/
   ```

4. **Update Documentation**: Add/update relevant documentation

5. **Add Tests**: Include tests for new functionality

### Pull Request Template

```markdown
## Description

Brief description of changes.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Golden dataset tests pass (if applicable)

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
```

### Review Process

1. **Automated Checks**: CI will run tests and linting
2. **Code Review**: Maintainers will review the code
3. **Feedback**: Address any feedback or requested changes
4. **Merge**: Once approved, the PR will be merged

---

## Release Process

### Version Bumping

Follow semantic versioning:
- **Major** (X.0.0): Breaking changes
- **Minor** (X.Y.0): New features, backwards compatible
- **Patch** (X.Y.Z): Bug fixes, backwards compatible

### Changelog

Update `CHANGELOG.md` with:
- New features
- Bug fixes
- Breaking changes
- Deprecations

### Release Steps

1. Update version in `pyproject.toml`
2. Update changelog
3. Create release PR
4. Tag release
5. Publish to PyPI (if applicable)

---

## Getting Help

### Documentation

- **README.md**: Quick start and overview
- **docs/API_REFERENCE.md**: Complete API documentation
- **docs/EXAMPLES.md**: Comprehensive examples
- **docs/STRATEGIES.md**: Strategy catalog

### Community

- **Issues**: Report bugs or request features
- **Discussions**: Ask questions or share ideas
- **Pull Requests**: Contribute code improvements

### Development

- **Code Review**: All changes require review
- **Testing**: Comprehensive test coverage expected
- **Documentation**: Keep docs up to date

Thank you for contributing to FinBrickLab! 🚀
