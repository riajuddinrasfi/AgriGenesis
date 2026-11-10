# AgriGenesis

AgriGenesis is a crop-planning web app. A set of agents and a **genetic algorithm** evolve a
plot-by-season crop rotation for a farm. Each candidate plan is tested in a farm simulator under
weather and market scenarios, then scored on risk-adjusted profit, soil health and constraints.
The app is built with [Streamlit](https://streamlit.io).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional: add GEMINI_API_KEY
streamlit run app.py
```

Open http://localhost:8501, pick a farm in the sidebar and click **Run optimisation**.

Run the tests with `pytest`.

## Dashboard

| Tab | What it shows |
|---|---|
| Overview | Expected and worst-case profit, the recommended rotation, findings, profit and resource use per season |
| Farm setup | Farm and soil profile, crop suitability per season, and the input datasets |
| Scenario lab | Profit per scenario, Monte Carlo risk (5th percentile, expected shortfall, probability of loss) and a custom what-if scenario |
| Evolution lab | GA convergence and population diversity, plus parameter experiments over several seeds |
| Strategy comparison | The GA plan against traditional rotation, monoculture, greedy and random plans; constraint check; export and save |
| Research report | A Markdown report you can download or save; written by Gemini when `GEMINI_API_KEY` is set |

## How it works

A plan is an integer matrix `genes[plot, season]` holding a crop index, or `-1` for fallow.

1. **Farm input agent**: loads the farm from `farms.csv` + `soil_profiles.csv` (or `sample_farm.json`) and validates it.
2. **Agronomy agent**: scores each crop's suitability per season from season type, soil pH and temperature, and builds the rotation matrix (same-family penalty, legume bonus).
3. **Scenario agent**: selects the weather and market scenarios and normalises their probabilities.
4. **Evolution agent**: runs the GA, seeded with the baseline strategies. It uses tournament selection, plot-wise or uniform crossover, mutation within allowed crops, elitism and early stopping.
5. **Simulation agent**: simulates the best plan in detail, checks resources and constraints, and runs a Monte Carlo analysis.
6. **Research agent**: writes rule-based findings and, if Gemini is configured, a narrative.

**Fitness** = expected profit − risk aversion × profit σ + soil-health value − constraint penalties.
Risk aversion scales with the farm's `risk_tolerance`. Budget, labour and crop suitability are hard
constraints. Planting the same crop family twice in a row is a soft constraint.

The **simulator** works season by season. Rainfall plus stored soil moisture covers part of each
crop's water need, and irrigation is shared out pro rata up to the farm's capacity. Yields are
adjusted for soil pH, temperature, drought, flooding, pests, soil nitrogen and rotation. Revenue
and cost include price and cost shocks.

## Project structure

```
app.py                 Streamlit entry point
config.py              paths and .env settings
agents/                orchestrator + farm input, agronomy, scenario, simulation, evolution, research agents
core/                  genetic algorithm: chromosome, population, fitness, selection, crossover, mutation, constraints
simulation/            farm, crop, soil, water, weather, economic simulators and scenario engine
services/              data loading/validation, strategies and baselines, reports, Gemini client
dashboard/             one module per dashboard tab
utils/                 calculations, normalisation, seeded randomness, helpers
data/                  sample datasets (see below)
outputs/               saved strategies, reports and charts (git-ignored)
tests/                 pytest suite
```

## Data

| File | Contents |
|---|---|
| `crops.csv` | crop, family, season type, growth days, yield, price, nitrogen effect |
| `crop_requirements.csv` | water need, pH and temperature range, labour, drought/flood tolerance, pest sensitivity |
| `input_costs.csv` | seed, fertiliser, pesticide and machinery cost per ha |
| `soil_profiles.csv` | soil type, pH, nitrogen index, organic matter, water-holding capacity |
| `farms.csv` | farm profiles (plots, area, climate, irrigation, budget, labour, risk tolerance), linked to a soil profile |
| `weather_scenarios.csv` | scenario probability and rainfall, temperature, price, cost, pest and yield shocks |
| `sample_farm.json` | sample farm plus seasons, economics, rotation, fitness, GA and simulation settings |

The sample numbers are illustrative and loosely based on Bangladesh agriculture. Replace them with
local data for real use.

## Gemini (optional)

Set `GEMINI_API_KEY` in `.env` (get a key at https://aistudio.google.com/apikey). The Research
report tab then shows a **Write narrative with Gemini** button. `GEMINI_MODEL` defaults to
`gemini-2.5-flash`. Without a key, or if a request fails, the app uses the rule-based research
agent. `.env` is git-ignored, so your key is never committed.
