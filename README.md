# Magents
**Multi-Agent Generative Trading System**  
This is a proof of concept for an AI-powered multi-strategy hedge fund simulation and backtesting framework.

## Overview

Magents is an open-source Python framework for a multi-strategy hedge fund backtesting and simulation system. The platform is designed as a multi-agent system in which independent strategy "pods" operate concurrently within a shared simulation environment. The goal is to enable realistic backtesting of multiple trading strategies under one umbrella, with unified data feeds and rigorous risk controls.


```mermaid
flowchart TD

    %% === DATA PIPELINE & MANAGEMENT ===
    DP[Data Pipeline] --> DM[Data Management]

    subgraph CentralTeam [Central Team Modules]
        DM
        RM[Risk Management]
    end

    %% === TRADING PODS SUBGRAPH ===
    subgraph Pods [Trading Pods (src/pods/strategies)]
        subgraph ELS [equity_long_short]
            ELS1(moving_average.py)
        end
        
        subgraph EV [event_driven]
            ED1(bill_ackman.py)
            ED2(congressional_trading.py)
        end
        
        subgraph FN [fundemental]
            FN1(fundamentals.py)
        end
        
        subgraph LB [long_biased]
            LB1(ben_graham.py)
            LB2(cathie_wood.py)
            LB3(warren_buffett.py)
        end

        subgraph MC [macro]
            MC1(stanley_druckenmiller.py)
        end
        
        subgraph MS [multi_strategy]
            MS1(__init__.py)
        end
        
        subgraph QN [quant]
            QN1(sentiment.py)
            QN2(sentiment_trading.py)
        end
    end

    %% === INTERACTIONS ===
    DM --> Pods
    Pods --> DM
    Pods --> RM
    RM --> Pods
    
    %% === BACKTESTING ENGINE ===
    Pods --> BE[Backtesting Engine]
    BE --> Pods

    %% === CLI INTERFACE ===
    CLI[CLI Interface] -.-> BE
```




### Key Features

- **Multi-Agent System**: Each trading strategy runs as an independent "pod" with its own agents  
- **Event-Driven Architecture**: Built on an event-driven foundation for realistic simulation  
- **Comprehensive Risk Management**: Central risk controls that monitor and enforce limits  
- **High-Fidelity Backtesting**: Realistic transaction costs, slippage, and order execution  
- **Modular Design**: Easily extend with new strategies, data sources, or risk rules  

---

### High-Level Table of Main Strategy Types

| **Strategy Category**  | **Definition Overview**                                                                                                                                                                                                                                                                                                  | **Example Path**                                  |
|------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| **Arbitrage**          | Looks for mispricings in the same (or closely related) instruments. Encompasses convertible bond arbitrage, tail protection trades, volatility arbitrage, opportunistic arbitrage, etc.                                                                                                                                   | `src/pods/strategies/arbitrage/`                  |
| **Credit**             | Focuses on debt instruments (corporate bonds, distressed debt, direct lending, structured credit, etc.), often employing long/short relative value trades or fundamental analysis of credit quality.                                                                                                                                     | `src/pods/strategies/credit/`                     |
| **Equity Long/Short**  | Invests in global equities, both long and short. Typically fundamental-driven (value or growth) but can also incorporate technical or tactical approaches. Sub-categories include US equity L/S, APAC, Europe, global, sector-focused, etc.                                                                                     | `src/pods/strategies/equity_ls/`                  |
| **Event Driven**       | Trades around corporate events (mergers, spin-offs, restructurings, activist campaigns). Includes merger arbitrage, activist strategies, and multi-event approaches.                                                                                                                                                     | `src/pods/strategies/event_driven/`               |
| **Long Biased**        | Primarily long-only or overwhelmingly net long. May focus on equities, commodities, or broader diversified growth portfolios, but uses hedge-fund-style structures (leverage, shorting in small measure, etc.).                                                                                                             | `src/pods/strategies/long_biased/`                |
| **Macro**              | Takes positions (directional or relative-value) in global macro instruments (currencies, bonds, equities, commodities) based on top-down fundamental or qualitative judgments. Sub-categories include fixed income relative value, commodity-focused macro, global macro, emerging markets macro, etc.                                        | `src/pods/strategies/macro/`                      |
| **Multi-Strategy**     | Allocates capital across multiple sub-strategies and asset classes. Often extremely diversified, with multiple PM teams under one fund umbrella.                                                                                                                                                                          | `src/pods/strategies/multi_strategy/`             |
| **Quant**              | Systematic strategies driven by algorithms. Can include CTA (trend-following on futures/FX), quant macro, statistical arbitrage, quant equity market neutral, or factor/risk-premia approaches.                                                                                                                            | `src/pods/strategies/quant/`                      |
| **Crypto**             | Focuses on digital assets (long-only, long/short, arbitrage, or market-neutral). Often a hybrid of fundamental and quantitative approaches.                                                                                                                                                                               | `src/pods/strategies/crypto/`                     |

Below are more detailed definitions for each category and example sub-strategies. You might use these definitions to guide your **Pod** design and structure within `src/pods/strategies/`.

---

## Installation

### Prerequisites

- Python 3.8 or higher
- [Poetry](https://python-poetry.org/) package manager

### Install with Poetry

```bash
# Clone the repository
git clone https://github.com/LLMQuant/magents.git
cd magents

# Install dependencies
poetry install

# Activate the virtual environment
poetry shell
```

---

## Usage

### Running a Backtest

```bash
# Basic backtest with default parameters
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL

# Backtest with custom time period and initial capital
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL \
    --start-date 2022-01-01 --end-date 2022-12-31 --initial-capital 1000000

# Run with specific strategies
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL \
    --strategies ma,congress

# Use a custom configuration file
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL \
    --strategies ma,value,sentiment --config config/default.yaml

# Generate an HTML report for the backtest
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL \
    --strategies ma,value --generate-report
```

### Using the Example Script

For a more complete example of how to run a multi-strategy backtest:

```bash
python examples/run_multi_strategy_backtest.py
```

This script demonstrates:

- Loading strategy configuration from a YAML file  
- Creating mock data if necessary  
- Running a backtest with multiple strategies  
- Generating visualizations and reports  

---

## Configuration System

Magents includes a flexible configuration system that allows you to customize all aspects of the backtesting process via YAML or JSON files.

Example configuration file (`config/default.yaml`):

```yaml
# Global Settings
global:
  initial_capital: 1000000.0  # Initial capital in USD
  max_leverage: 2.0           # Maximum allowed leverage
  transaction_cost: 0.001     # 10 basis points per trade

# Strategy-specific Settings
strategies:
  ma:
    fast_window: 10
    slow_window: 30

  value:
    signal_threshold: 0.65
    max_positions: 5
```

You can specify configuration files via the CLI:

```bash
python -m src.main --config config/default.yaml
```

---

## Available Strategies

The framework already includes a few built-in example strategy pods:

1. **Moving Average Crossover (`ma`)**  
   A simple strategy that generates buy/sell signals based on the crossing of fast and slow moving averages.

2. **Congressional Trading (`congress`)**  
   A strategy that looks at companies possibly impacted by policy changes or legislation, attempting to identify potential beneficiaries of new regulatory or government contracting opportunities.

3. **Value Investing (`value`)**  
   A fundamental strategy that uses valuation measures (like P/E ratios, balance sheet strength, Graham Number) to find mispriced securities.

4. **Sentiment Trading (`sentiment`)**  
   A strategy that aggregates insider activity and sentiment data (news, social media) to form trading signals.

Feel free to adapt or extend these examples, or replace them altogether with your own ideas.

---

## Creating Custom Strategy Pods

To add your own strategy:

1. Create a new file in `src/pods/strategies/` (e.g. `src/pods/strategies/my_strategy.py`).  
2. Implement one or more *agents* (signal agent, execution agent, etc.) in that file:  
   - A **signal agent** might generate trade signals based on your logic (technical, fundamental, sentiment, etc.).  
   - An **execution agent** might convert signals into actual orders.  
3. Combine these agents into a **Pod** (a Python class) that orchestrates their actions.  
4. Register your new Pod in `src/pods/strategies/factory.py` (so that the CLI and engine can discover it).  

---

## Hedge Fund Strategy Classifications & Example Pod Structure

Below is a more comprehensive overview of hedge fund strategy types, which you can use to inspire how you organize and name your strategy pods in Magents. For each main strategy category (Arbitrage, Credit, Equity Long/Short, Event Driven, Long Biased, Macro, Multi-Strategy, Quant, Crypto), we list typical sub-strategies and provide high-level definitions. You can create corresponding `.py` files in `src/pods/strategies/<category>/` for each sub-strategy you wish to implement. For example, a **convertible bond arbitrage** strategy might live at:

```
src/pods/strategies/arbitrage/convertible_bond_arbitrage.py
```

Each sub-strategy can have different agents (signal generation, risk filters, execution logic) that reflect the nuances of that strategy.



### 1. Arbitrage  
**January 25 performance**: +0.78% (12-month performance +6.29%, five-year CAR +5.14%)

**General Definition**: Strategies that attempt to capture risk-free (or low-risk) profits by exploiting mispricings of the same or closely related instruments.  
Typical sub-strategies include:  
- **Convertible Bond Arbitrage (CB)**  
- **Tail Protection (Tail)**  
- **Volatility Arbitrage (Vol)**  
- **Opportunistic Arbitrage (Opp)**  

Suggested directory for implementation:  
```
src/pods/strategies/arbitrage/
  ├── convertible_bond_arbitrage.py
  ├── tail_protection.py
  ├── volatility_arbitrage.py
  └── opportunistic_arbitrage.py
```

---

### 2. Credit  
**January 25 performance**: +0.95% (12-month performance +9.80%, five-year CAR +5.59%)

**General Definition**: Strategies focusing on debt instruments and credit-like exposures (corporate bonds, structured credit, direct lending, distressed debt).  
Typical sub-strategies include:  
- **Credit Relative Value (RV)**  
- **Direct Lending (Dir Len)**  
- **Distressed Credit (Distress)**  
- **Multi-Credit (Multi)**  
- **Municipal Credit (Muni)**  
- **Structured Credit (Struct)**  
- **Structured Credit Long-Only (StrucLO)**  

Suggested directory for implementation:  
```
src/pods/strategies/credit/
  ├── credit_relative_value.py
  ├── direct_lending.py
  ├── distressed_credit.py
  ├── multi_credit.py
  ├── municipal_credit.py
  ├── structured_credit.py
  └── structured_credit_lo.py
```

---

### 3. Equity Long/Short  
**January 25 performance**: +2.22% (12-month performance +14.51%, five-year CAR +7.79%)

**General Definition**: Investing in global equities on the long and short side. Most strategies have a fundamental bias (value/growth). Some are more technical/tactical, incorporating positioning/flow data.  
Typical sub-strategies include:  
- **US Equity L/S (US)**  
- **Asia Pacific Equity L/S (APAC)**  
- **European Equity L/S (EUR)**  
- **Global Equity L/S (Global)**  
- **Fundamental Equity Market Neutral (FEMN)**  
- **Sector Long/Short (Sector)**  
- **Other L/S (Other)**  

Suggested directory for implementation:  
```
src/pods/strategies/equity_ls/
  ├── us_equity_ls.py
  ├── apac_equity_ls.py
  ├── eur_equity_ls.py
  ├── global_equity_ls.py
  ├── femn.py  # Fundamental Equity Market Neutral
  ├── sector_long_short.py
  └── other_ls.py
```

---

### 4. Event Driven  
**January 25 performance**: +1.80% (12-month performance +11.87%, five-year CAR +8.16%)

**General Definition**: Strategies that invest around corporate events (M&A, spin-offs, restructuring, activism). Identifies mispriced securities with favorable risk/reward based on catalysts or event outcomes.  
Typical sub-strategies include:  
- **Activist (Activist)**  
- **Merger Arbitrage (M&A)**  
- **Event-Driven Multi-Strategy (Multi)**  
- **Event-Driven Opportunistic (Opp)**  

Suggested directory for implementation:  
```
src/pods/strategies/event_driven/
  ├── activist.py
  ├── merger_arbitrage.py
  ├── multi_event_driven.py
  └── opportunistic_event.py
```

---

### 5. Long Biased  
**January 25 performance**: +3.19% (12-month performance +13.99%, five-year CAR +6.56%)

**General Definition**: Overwhelmingly net-long strategies, covering multiple asset classes (equities, commodities, etc.) but still structured like hedge funds (may use some leverage, limited shorts).  
Typical sub-strategies include:  
- **Equities (Equity)**  
- **Diversified Growth (Div Growth)**  
- **Commodities (Commods)**  
- **Other (Other)**  

Suggested directory for implementation:  
```
src/pods/strategies/long_biased/
  ├── equities_long_biased.py
  ├── diversified_growth.py
  ├── commodities_long_biased.py
  └── other_long_biased.py
```

---

### 6. Macro  
**January 25 performance**: +1.32% (12-month performance +10.73%, five-year CAR +6.20%)

**General Definition**: Takes positions (directional or relative-value) in global markets (FX, rates, equity indexes, commodities) guided by top-down macro views. Sub-strategies may emphasize emerging markets, commodity themes, or fixed-income relative value.  
Typical sub-strategies include:  
- **Fixed Income Relative Value (FIRV)**  
- **Commodities (Commods)**  
- **Global Macro (Global)**  
- **Emerging Markets Macro (EM)**  

Suggested directory for implementation:  
```
src/pods/strategies/macro/
  ├── fixed_income_rv.py
  ├── macro_commodities.py
  ├── global_macro.py
  └── emerging_markets_macro.py
```

---

### 7. Multi-Strategy  
**January 25 performance**: +1.33% (12-month performance +13.14%, five-year CAR +11.24%)

**General Definition**: Capital is deployed across multiple sub-strategies and asset classes, often with distinct PM/risk-taking teams. Extremely diversified approach.  
If you want to build a multi-strategy “umbrella” that contains multiple sub-pods *within* it, you can do so by creating one overarching strategy pod that internally references others.  

Suggested directory for implementation:  
```
src/pods/strategies/multi_strategy/
  └── multi_strategy_master.py
```

---

### 8. Quant  
**January 25 performance**: +2.45% (12-month performance +9.31%, five-year CAR +5.02%)

**General Definition**: Systematic strategies that rely on algorithmic decision-making. May include CTA (trend-following), stat arb, quant macro, factor-based equity market neutral, alternative risk premia, etc.  
Typical sub-strategies include:  
- **CTA (CTA)**  
- **Quant Macro / Global Asset Allocation (Macro)**  
- **Quant Multi-Strategy (Multi)**  
- **Statistical Arbitrage (Stat Arb)**  
- **Quant Equity Market Neutral (EMN)**  
- **Risk Premia (RP)**  

Suggested directory for implementation:  
```
src/pods/strategies/quant/
  ├── cta.py
  ├── quant_macro.py
  ├── quant_multi_strategy.py
  ├── stat_arb.py
  ├── quant_equity_market_neutral.py
  └── risk_premia.py
```

---

### 9. Crypto  
**General Definition**: Invests in digital assets (e.g. cryptocurrencies, tokens). Can be long-only, market-neutral, or a multi-strategy approach with fundamental or quantitative signals.

Suggested directory for implementation:
```
src/pods/strategies/crypto/
  ├── crypto_long_short.py
  ├── crypto_arbitrage.py
  └── multi_crypto_strategy.py
```

> **Note**: The performance figures above (January 25 returns, 12-month, 5-year CAR) are illustrative and derived from the example data in the prompt. They do *not* reflect actual real-time performance. If you want to track or display strategy performance, you can configure your own analytics or read from an external data file.

---

## Visualization and Reporting

Magents includes a set of tools for visualizing backtest results:

- Equity curves and drawdowns  
- Performance metrics (Sharpe, CAGR, etc.)  
- Monthly or yearly returns heatmaps  
- Trade-by-trade analysis  
- HTML report generation  

Example command to generate an HTML backtest report:

```bash
python -m src.main --data-dir /path/to/data --instruments AAPL,MSFT,GOOGL \
    --strategies ma,value --generate-report --report-dir results
```

---

## Project Structure

```
magents/
├── src/
│   ├── core/
│   │   ├── engine.py             # Backtesting engine
│   │   ├── portfolio.py          # Portfolio tracking
│   │   ├── order.py              # Order types & execution
│   │   ├── event.py              # Event system
│   ├── data/
│   │   ├── pipeline.py           # Data ingestion pipeline
│   │   ├── management.py         # Data preprocessing/distribution
│   │   ├── feeds/                # Data source implementations
│   │       ├── market_data.py
│   │       ├── sentiment.py
│   ├── risk/
│   │   ├── manager.py            # Central risk management
│   │   ├── limits.py             # Risk limits & rules
│   │   ├── metrics.py            # Risk metrics
│   ├── pods/
│   │   ├── base.py               # Base pod class
│   │   ├── agents/
│   │   │   ├── base_agent.py
│   │   │   ├── signal_agent.py
│   │   │   └── execution_agent.py
│   │   ├── strategies/           # Example strategies + your custom pods
│   │       ├── moving_average.py
│   │       ├── congressional_trading.py
│   │       ├── ...
│   ├── cli/
│   │   ├── commands.py           # CLI commands
│   │   ├── config.py             # Config handling
│   │   ├── reporting.py          # Results/visualization
│   ├── utils/
│   │   ├── messaging.py          # Inter-agent messaging
│   │   ├── logger.py             # Logging utilities
│   │   ├── performance.py        # Performance metrics
│   ├── main.py                   # Main entry point
├── tests/                        # Test suite
├── examples/                     # Example configurations
├── docs/                         # Documentation
├── pyproject.toml                # Poetry config
├── README.md                     # This document
```

---

## Contributing

Contributions are welcome! Please:

1. **Fork** the project  
2. **Create** your feature branch (`git checkout -b feature/my-feature`)  
3. **Commit** your changes (`git commit -m 'Add my feature'`)  
4. **Push** to the branch (`git push origin feature/my-feature`)  
5. **Open a Pull Request**  

You can contribute new strategy pods, improve the backtesting engine, enhance risk management features, or add entirely new data feeds.

---

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

---

## Acknowledgements

Inspired by real-world multi-strategy hedge funds and various open-source quant frameworks. By providing a realistic simulation environment, we hope to support strategy research, prototyping, and learning for traders, quants, and students alike.