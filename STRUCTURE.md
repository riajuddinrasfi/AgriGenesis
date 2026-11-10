# AgriGenesis — Project Structure

Every folder has one job. Data flows top to bottom:

```text
Farm Input → Validation → Agronomy → Scenario Setup → Evolution (GA ⇄ Simulation) → Research → Final Result
```

`agents/orchestrator.py` runs this pipeline. `app.py` and the `dashboard/` pages call it and show the results.

## Folder tree

```text
AgriGenesis/
├── app.py                      # Streamlit entry point: streamlit run app.py
├── config.py                   # Paths, seasons, planting windows, GA defaults, fitness weights, scenario limits, Gemini settings
├── requirements.txt            # Python dependencies
├── pytest.ini                  # pytest settings (test path = tests/)
├── README.md                   # Overview, setup, run and test instructions
├── STRUCTURE.md                # This file
├── .env.example                # Template for the optional GEMINI_API_KEY / GEMINI_MODEL
├── .env                        # Your local secrets (git-ignored, never committed)
├── .gitignore
├── .streamlit/
│   └── config.toml             # Dark theme with purple accent
│
├── agents/                     # One agent per pipeline step
│   ├── orchestrator.py         # Runs the full pipeline and returns the result dictionary
│   ├── farm_input_agent.py     # Form input or natural-language text → validated FarmProfile
│   ├── agronomy_agent.py       # Crop-season, soil, pH and duration checks → feasible crops per season
│   ├── scenario_agent.py       # Built-in scenarios + custom scenarios (numbers or text)
│   ├── simulation_agent.py     # Single entry point for running the farm simulator
│   ├── evolution_agent.py      # Configures and runs the Genetic Algorithm (never calls Gemini)
│   └── research_agent.py       # Explains results from real numbers; optional Gemini wording
│
├── core/                       # Custom Genetic Algorithm
│   ├── chromosome.py           # Gene(plot_id, season, crop_id, water_level, fertilizer_level, planting_window)
│   ├── population.py           # Random genes/chromosomes and the initial population
│   ├── fitness.py              # Weighted, normalised fitness from scenario simulations
│   ├── selection.py            # Tournament selection and elite picking
│   ├── crossover.py            # Uniform and single-point crossover
│   ├── mutation.py             # Changes crop, water, fertilizer or planting window
│   ├── constraints.py          # Land, budget, water and crop-season checks + repair
│   └── genetic_algorithm.py    # Evolution loop with elitism and convergence history
│
├── simulation/                 # Deterministic agricultural simulator
│   ├── farm_simulator.py       # Whole farm, one scenario; soil health carries over between seasons
│   ├── crop_simulator.py       # yield = area × base × water × soil × weather × nutrient
│   ├── soil_simulator.py       # pH, fertility, fertilizer response, soil-health change
│   ├── water_simulator.py      # Effective rain, irrigation, water stress and waterlogging
│   ├── weather_simulator.py    # Scenario definition, rainfall and planting-window factors
│   ├── economic_simulator.py   # Seed, fertilizer, labor and irrigation costs; revenue
│   └── scenario_engine.py      # Runs a strategy under many scenarios; resilience score
│
├── services/                   # Shared services
│   ├── data_loader.py          # Loads and validates the data/ files
│   ├── validation_service.py   # Farm input and weight validation
│   ├── gemini_service.py       # All Gemini calls; returns None when unavailable
│   ├── strategy_service.py     # GA output → readable records; saves to outputs/strategies/
│   └── report_service.py       # Markdown research report; saves to outputs/reports/
│
├── data/                       # Synthetic sample data (every file has a data_note)
│   ├── crops.csv               # Base yield (t/ha), price (USD/t), growth days, crop family
│   ├── crop_requirements.csv   # Seasons, soils, pH range, water (mm), fertilizer (kg/ha), tolerances, soil effect
│   ├── input_costs.csv         # Seed and labor (USD/ha), fertilizer (USD/kg), irrigation (USD/m³)
│   ├── soil_profiles.csv       # Fertility, effective-rainfall fraction, drainage per soil type
│   ├── farms.csv               # Sample farms (area, plots, soil, water, budget, rainfall)
│   ├── weather_scenarios.csv   # Normal, drought, excess rainfall, input-price shock, market-price drop
│   └── sample_farm.json        # Default farm loaded at start-up
│
├── dashboard/                  # Streamlit pages
│   ├── __init__.py             # Theme, Plotly styling, session state, shared helpers
│   ├── overview.py             # Farm summary, status and key results
│   ├── farm_setup.py           # Form, natural-language input, validation, weights
│   ├── scenario_lab.py         # Choose / create scenarios, stress-test the best plan
│   ├── evolution_lab.py        # GA settings, run button, live convergence chart
│   ├── strategy_comparison.py  # Top strategies side by side
│   └── research_report.py      # Final plan, costs, risks, explanation, download
│
├── utils/                      # Small helpers
│   ├── calculations.py         # Unit conversions, range checks
│   ├── normalization.py        # clip, min-max, safe ratios
│   ├── random_generator.py     # Seeded random numbers
│   └── helpers.py              # Formatting and serialisation
│
├── outputs/                    # Generated files (git-ignored except .gitkeep)
│   ├── strategies/             # Saved strategy JSON
│   ├── reports/                # Saved Markdown reports
│   └── charts/                 # Exported charts
│
└── tests/                      # pytest suite: python -m pytest -q
    ├── conftest.py                     # Shared fixtures (datasets, sample farm, context)
    ├── test_data_loader.py             # Dataset loading and validation errors
    ├── test_simulation.py              # Simulator behaviour and scenarios
    ├── test_simulation_components.py   # Each simulation module + all five scenarios
    ├── test_constraints.py             # Input validation, agronomy, repair
    ├── test_fitness.py                 # Weighted normalised fitness
    ├── test_genetic_algorithm.py       # Population, operators, GA runs, orchestrator
    ├── test_ga_evolution.py            # Elitism, seeds, full default run, no Gemini in GA
    ├── test_gemini_service.py          # Gemini fallbacks (no network)
    └── test_app.py                     # Streamlit AppTest across all six pages
```

## How the pieces call each other

```text
app.py ──► dashboard/* ──► agents/orchestrator.py
                              ├─► farm_input_agent ──► services/validation_service (+ gemini_service, optional)
                              ├─► agronomy_agent   ──► services/data_loader (data/*.csv)
                              ├─► scenario_agent   ──► simulation/scenario_engine (+ gemini_service, optional)
                              ├─► evolution_agent  ──► core/genetic_algorithm ──► core/fitness ──► simulation/farm_simulator
                              ├─► simulation_agent ──► simulation/farm_simulator
                              └─► research_agent   ──► services/report_service (+ gemini_service, optional)
```

Gemini is only used for text: parsing farm and scenario descriptions, and wording explanations. All numbers come from `core/` and `simulation/`.
