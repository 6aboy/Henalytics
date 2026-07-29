# Henalytics ML TODO

## Completed

- [x] Phase 1: Inspect existing Django project and current forecasting flow.
- [x] Phase 2: Create `ml/` structure.
- [x] Phase 3: Build `ml/train.py` for cleaned CSV SARIMAX training.
- [x] Phase 4: Build `ml/predict.py` for saved-model forecasting.
- [x] Phase 5: Add Django integration through an experimental Forecasting page.
- [x] Phase 6: Reuse existing forecast models and avoid duplicate database tables.
- [x] Phase 7: Return forecast rows with date, predicted pieces, confidence bounds, and model version.
- [x] Phase 8: Add Django management commands for training and experimental forecasting.
- [x] Phase 9: Add `ml/requirements.txt` without replacing the root Django requirements.
- [x] Phase 10: Add focused ML and Django tests.
- [x] Phase 11: Document ML workflow in `ml/README.md`.

## Next Improvements

- [ ] Tune SARIMAX orders to reduce convergence warnings.
- [ ] Add optional user-entered future assumptions for bird count, dead birds, culls, and feed.
- [ ] Decide whether the experimental model should replace or supplement the existing Analytics page.
- [ ] Add model artifact cleanup if many versions are saved later.
