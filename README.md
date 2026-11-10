# AgriGenesis — An Evolutionary Agriculture Strategy Laboratory

AgriGenesis optimises an **entire farm strategy**: which crop to grow on every plot in every season, how much to
irrigate and fertilise, and when to plant. A custom **Genetic Algorithm (GA)** evolves candidate strategies and a
**deterministic agricultural simulator** scores each one under several weather and market scenarios. Gemini is
optional and only turns text into structured input and numbers into explanations.

> **Data notice:** all crop, soil, cost, price and weather figures in `data/` are synthetic sample data created for
> this demo. They are not verified agricultural research or real market prices.

## Problem

A small farm has limited land, water and money, several seasons and crops that differ in yield, price, water need,
soil impact and sensitivity to drought or flooding. Good choices interact: a thirsty monsoon crop leaves less water
for winter, repeating a crop family wears out the soil and the most profitable plan may collapse in a drought.
Comparing every combination by hand is impossible (4 plots x 3 seasons x 9 crops x management options).

## Solution

1. Describe the farm with a form or in plain language.
2. Agronomy rules work out which crops can grow in each season on this soil.
3. The GA evolves whole-farm plans. Every candidate is repaired to respect the constraints, then simulated under
   normal, drought, excess-rain, input-price and market-price scenarios.
4. A weighted fitness balances profit, yield, water efficiency, soil health and resilience.
5. The dashboard shows convergence, the best plans side by side, scenario stress tests and a research report.

## Architecture

```
Farm Input -> Validation -> Agronomy -> Scenario Setup -> Evolution (GA) <-> Simulation -> Research -> Final Result
```

| Folder | Contents |
|---|---|
| `agents/` | Six pipeline agents and the `Orchestrator` that runs them |
| `core/` | GA: chromosome, population, fitness, selection, crossover, mutation, constraints and repair |
| `simulation/` | Deterministic crop, soil, water, weather, economic, farm and scenario models |
| `services/` | Data loading, validation, Gemini wrapper, strategy serialisation, report building |
| `dashboard/` | The six Streamlit pages |
| `utils/` | Small numeric, random and I/O helpers |
| `data/` | Synthetic CSV datasets and `sample_farm.json` |
| `outputs/` | Saved strategies (JSON) and reports (Markdown) |
| `tests/` | pytest suite, including a Streamlit `AppTest` run of the whole dashboard |

### Agents

| Agent | Responsibility |
|---|---|
| Farm Input (`farm_input_agent.py`) | Form input or natural language (Gemini, with a rule-based parser fallback) to a validated `FarmProfile`. Missing or invalid numbers are reported, never silently defaulted. |
| Agronomy (`agronomy_agent.py`) | Checks crop-season, soil, pH, growing duration, water, fertiliser and cost feasibility from the datasets. |
| Scenario (`scenario_agent.py`) | Loads built-in scenarios, builds custom ones from parameters or text (Gemini or keyword rules; values clamped). |
| Simulation (`simulation_agent.py`) | Runs the farm simulator for a plan under one or many scenarios. |
| Evolution (`evolution_agent.py`) | Configures and runs the GA; returns the best plan, ranked plans and convergence history. |
| Research (`research_agent.py`) | Explains the results from the real numbers (Gemini or a template) and flags AI numbers that don't match. |
| Orchestrator (`orchestrator.py`) | Runs the full pipeline once and returns `farm_profile`, `validation_results`, `scenarios`, `best_strategy`, `ranked_strategies`, `best_fitness`, `fitness_history`, `simulation_metrics`, `scenario_results`, `research_report`, `assumptions`. |

## Genetic Algorithm

**Chromosome:** one gene per plot-season slot:
`plot_id, season, crop_id (or FALLOW), water_level 0-1, fertilizer_level 0-1, planting_window (Early/On-time/Late)`.

| Step | Implementation |
|---|---|
| Initialisation | Random feasible genes, repaired, distinct where possible (`core/population.py`) |
| Fitness | Simulate under every selected scenario (`core/fitness.py`), cached per chromosome |
| Selection | Tournament of size 3 (`core/selection.py`) |
| Crossover | Uniform per slot (or single-point), probability 0.80 (`core/crossover.py`) |
| Mutation | Per gene, probability 0.10: change crop, water, fertiliser or window (`core/mutation.py`) |
| Repair | After crossover and mutation: fix crop-season / window errors, clip levels, scale irrigation to the water limit, drop the least profitable plantings until the budget fits (`core/constraints.py`) |
| Elitism | Best 2 survive unchanged |
| Defaults | Population 50, 20 generations, seed 42 (all configurable in the Evolution Lab) |

**Fitness** = 0.35 profit + 0.20 yield + 0.15 water + 0.15 soil + 0.15 resilience. Each score is normalised to 0-1:

- profit: net profit between `-budget` and a per-farm profit ceiling (best crop per slot, fully managed)
- yield: achieved / potential yield of the chosen crops
- water: 1 - water used / water available
- soil: final soil-health index / 100
- resilience: mean share of normal-condition profit kept across adverse scenarios

Weights are set in Farm Setup and normalised to sum to 1.

## Simulation assumptions

> The simulator is a transparent demonstration model running on synthetic data. It is not scientifically validated and its outputs are not agronomic advice.


```
yield = area x base_yield x water_factor x soil_factor x weather_factor x nutrient_factor
```

- **Water:** effective rain (rain x soil retention) plus irrigation (`water_level` x irrigation need). Supply above
  the requirement adds no yield; above 110% a waterlogging penalty grows with excess, crop sensitivity and poor
  drainage. Drought-tolerant crops lose less yield when short of water. If total irrigation exceeds the
  scenario's available water, all irrigation is scaled down.
- **Soil:** soil fertility, pH fit (marginal pH costs yield) and the plot's soil-health index. Soil health carries
  over between seasons; legumes raise it, heavy feeders lower it, repeating a crop family lowers it, fallow rests it.
- **Nutrients:** diminishing returns from fertiliser relative to the crop's requirement.
- **Weather:** scenario yield stress and planting-window timing (late planting costs yield).
- **Economics:** revenue = yield x price x market multiplier; costs = seed + labour + fertiliser + irrigation, each
  scaled by the input-cost multiplier; profit = revenue - costs.
- Budget and water limits are enforced against normal conditions; plots are equal in size.

## Datasets (`data/`, synthetic)

| File | Contents |
|---|---|
| `crops.csv` | 9 crops: family, base yield (t/ha), price (USD/t), growth duration |
| `crop_requirements.csv` | Allowed seasons, suitable soils, pH range, water and fertiliser need, drought / waterlogging tolerance, soil-health effect |
| `input_costs.csv` | Seed and labour cost per ha, fertiliser per kg, irrigation per m3 |
| `soil_profiles.csv` | 4 soil types: fertility, rain retention, drainage |
| `farms.csv` | 3 example farms |
| `weather_scenarios.csv` | Normal, drought, excess rainfall, input-price shock, market-price drop multipliers |
| `sample_farm.json` | Default 4 ha, 4-plot farm loaded at start-up |

Every file carries a `data_note` marking it as synthetic. `services/data_loader.py` checks the files on load:
- all required columns are present and IDs are unique
- numbers are within their allowed ranges and units, `min_ph < max_ph`, and seasons are valid
- crop, soil and scenario references match across files, and the `normal` scenario exists

A missing file, malformed CSV/JSON or invalid value raises a `DataError` naming the file, row and column.

## Project structure

```text
AgriGenesis/
├── app.py, config.py        # Streamlit entry point and central configuration
├── agents/                  # Orchestrator + 6 pipeline agents
├── core/                    # Genetic Algorithm (chromosome, operators, constraints, fitness)
├── simulation/              # Deterministic crop, soil, water, weather and economic simulator
├── services/                # Data loading, validation, Gemini, strategy and report services
├── data/                    # Synthetic CSV datasets and sample_farm.json
├── dashboard/               # Six Streamlit pages
├── utils/                   # Small numeric and formatting helpers
├── outputs/                 # Saved strategies, reports and charts
└── tests/                   # pytest suite
```

See [STRUCTURE.md](STRUCTURE.md) for every file and how the modules call each other.

## Local setup

Requires Python 3.10+ (developed and tested on Python 3.13).

```bash
git clone https://github.com/riajuddinrasfi/AgriGenesis.git
cd AgriGenesis
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501. No API key is needed: every feature has a deterministic fallback.

## Gemini configuration (optional)

1. Create a key at https://aistudio.google.com/apikey.
2. Copy the template and fill it in. `.env` is git-ignored; never commit it.

```bash
cp .env.example .env
```

```ini
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-3.5-flash   # optional; this is the default
GEMINI_TIMEOUT_S=30             # optional; per-request timeout before falling back
```

Settings are read from environment variables first, then from Streamlit secrets (`.streamlit/secrets.toml` or
the Community Cloud *Secrets* box). The Overview page shows whether Gemini is connected.

What Gemini does: parse a plain-language farm description, interpret a custom scenario description, and word the
research report. What it never does: compute or change any number. Simulation, constraints, fitness and the GA
are plain Python and never call Gemini. Gemini output is schema-checked; numbers in AI text that don't match the
simulation results are flagged in the report.

If a call fails (bad key, quota, unknown or overloaded model, timeout), the app shows the reason (with any key
masked) and continues with the rule-based parser or template report. Google retires model names over time; if
the report warning says "model not found", set `GEMINI_MODEL` to a current model.

## Deploying to Streamlit Community Cloud

1. Push the repository to GitHub (the code must be on the branch you deploy, e.g. `main`).
2. Go to https://share.streamlit.io, click **Create app**, and choose the repo, branch and `app.py` as the main file.
3. Under **Advanced settings**, pick a Python version (3.11+ recommended) and paste into **Secrets**:

   ```toml
   GEMINI_API_KEY = "your-key"
   GEMINI_MODEL = "gemini-3.5-flash"
   ```

4. Click **Deploy**. Dependencies install from `requirements.txt`; the dark theme comes from `.streamlit/config.toml`.

Leave the secrets out to deploy the no-Gemini version. Community Cloud's file system is temporary, so files
written to `outputs/` disappear on restart; use the dashboard's download buttons to keep reports.

Other hosts: `pip install -r requirements.txt` then
`streamlit run app.py --server.headless true --server.port 8501`, with `GEMINI_API_KEY` set as an environment
variable.

## Using the dashboard

| Page | What you do |
|---|---|
| Overview | Status of the current farm, the last optimisation run and Gemini |
| Farm Setup | Load a sample farm, edit the form or describe the farm in words; set optimisation priorities; click **Validate farm** |
| Scenario Lab | Choose the built-in scenarios, add custom ones (sliders or text) and stress-test the best plan |
| Evolution Lab | Set GA parameters and click **Evolve My Farm**; watch the live fitness chart |
| Strategy Comparison | Rank and compare the top strategies, their scenario profits and plans |
| Research Report | Economics, risks, assumptions and the explanation (Gemini or rule-based); download Markdown |

Results are kept in Streamlit session state: changing pages never re-runs the optimiser. If you change the farm,
priorities or scenarios after a run, the app warns that the result is out of date until you evolve again. Each run
is also saved to `outputs/strategies/`.

## Demo script (about 3 minutes)

1. **Problem (20 s).** "A 4-hectare farm, 4 plots, 3 seasons, 9 crops, plus water, fertiliser and planting-time
   choices: far too many combinations to compare by hand, and the most profitable plan may collapse in a drought."
2. **Farm Setup (30 s).** Load *Green Valley Farm*. Show the natural-language box: paste a description and click
   *Parse description*. Move the *Resilience* priority up a little. Click **Validate farm** and show the crop
   suitability table.
3. **Scenario Lab (20 s).** Point at the five built-in scenarios. Type "fertiliser prices rise 40%" and click
   *Interpret and add*.
4. **Evolution Lab (40 s).** Click **Evolve My Farm** with the defaults (population 50, 20 generations). Narrate
   the live chart: best and mean fitness climbing as the GA selects, crosses, mutates and repairs plans. Show the
   best plan's crop grid.
5. **Strategy Comparison (30 s).** Compare the top 5 plans: profit vs resilience vs water. Open the scenario
   heatmap.
6. **Scenario Lab again (20 s).** Click *Evaluate best strategy under these scenarios* and show how profit holds up
   in the drought and market-drop cases.
7. **Research Report (20 s).** Show the explanation (Gemini if configured, rule-based otherwise) and download the
   report. Close with: "All data is synthetic; this demonstrates the method, not agronomic advice."

## Testing

```bash
python -m pytest -q
```

The suite covers dataset loading and validation, farm validation, agronomy rules, every simulator component,
constraint checks and repair, fitness, selection, crossover, mutation, population initialisation, full GA runs,
the Gemini service and every agent with Gemini off and with a fake Gemini client, an end-to-end run of the whole
pipeline (`tests/test_end_to_end.py`) and the full dashboard journey through Streamlit `AppTest`
(`tests/test_app.py`). A real Gemini call is not part of the suite because it needs a key and network access.

## Known simulation limitations

- **Synthetic data.** Every crop, soil, cost, price and scenario value is invented for the demo. Results show how
  the method works; they are not agronomic or financial advice and the model is not scientifically validated.
- **One planning year.** Seasons within one year only; no multi-year rotations, price dynamics or inflation.
  Water is a single yearly pool shared by all seasons.
- **Simplified agronomy.** Yield is a product of multiplicative factors (water, soil, weather, nutrients). There are
  no pests, diseases, weeds, intercropping, crop stages, daily weather, temperature or evapotranspiration models.
- **Uniform plots.** All plots are equal in size and share one soil type, one pH and one water pool.
- **Fixed scenarios.** Scenarios are deterministic multipliers applied to the whole year, not probabilistic
  weather; resilience is the average profit kept across the chosen adverse scenarios, not a risk measure such as
  value-at-risk.
- **Water and budget limits are enforced under normal conditions.** Under drought, irrigation is scaled down to the
  reduced supply instead of re-planning.
- **Heuristic search.** The GA finds good plans, not guaranteed optimal ones; results depend on the seed, population
  size, generations and weights.
- **Fitness normalisation is farm-relative.** Scores compare plans for the same farm and cannot be compared across
  farms.
