# Terrain model card and evaluation

## Intended use

The 32-dimensional convolutional autoencoder encodes 64×64 patch-relative DEM terrain. `scripts/train_terrain_encoder.py` trains it on Earth patches; `scripts/build_hybrid_matches.py` screens Earth patches by five physical features, selects the nearest 50, then reranks that shortlist by Euclidean embedding distance. It is a research retrieval aid, not a landing-site or mission-operations decision model.

## Verified configuration and metrics

`models/terrain_encoder/training_metadata.json` records seed 42, 15 training tiles / 3 validation tiles, 3,078 training patches / 427 validation patches, eight epochs, Adam learning rate 0.001, a fixed 200 m normalization scale and clipping at ±5 normalized units. The best saved validation masked MSE is 0.0106154 in normalized units at epoch seven. The checkpoint SHA-256 at audit time was `306066489a3e3c5c8a1cfc925a2d40025a7ad110ef7e1710da4f3c9bb613e13b`.

On 2026-11-15, the checkpoint was reloaded with `weights_only=True`; inference was rerun over the three named validation archives using valid-pixel masks and the training preprocessing. Across 427 patches and 1,742,419 valid pixels, reconstruction MAE was **12.0199 m** and RMSE **20.6069 m** against the clipped training target. No validation pixels exceeded the ±1,000 m clipping threshold in this set. These are reconstruction metrics, not terrain-match accuracy. The original training split is whole-tile holdout; nearby or related geography across tiles has not been independently ruled out.

The read-only reproduction command is `.venv/bin/python -m scripts.evaluate_saved_checkpoint`. It returned 12.0199260478 m MAE and 20.6069403968 m RMSE on 2026-11-15 without writing the checkpoint or a ranking. The saved best validation MSE describes the epoch selected during training; the reproduction reuses that validation split, so it is not a fresh test set.

## Experimental retrieval evidence

- Baseline Mars: 255 target patches, 3,505 Earth indexed patches, top five per target.
- Expanded Mars: 255 targets, 3,736 indexed Earth patches. The larger index changes rankings; it does not by itself demonstrate improvement in relevance. Seventy-four unique coordinates in expanded top fives were absent from baseline top fives; this is not a count of newly acquired sites.
- Moon Site04: four available lunar patches, two selected for retrieval against 3,762 Earth patches. First target's saved top neural distance is about 22.60, much larger than the first baseline Mars patch's about 2.74. Cross-domain distances are uncalibrated; their magnitudes are a warning, not probabilities.
- `outputs/neural/evaluation.json` compares baseline physical and neural winners: top-one agreement is 4/255. This is rank disagreement, not evidence that either method is correct. The hybrid shortlist of 50 means global neural top candidates outside the physical shortlist cannot be retrieved.
- Independent read-only recomputation from the saved embedding arrays and five feature CSV columns reproduced the neural-only and hybrid **top-five patch IDs for all 255 Mars targets** in both the 3,505- and 3,736-Earth indexes. Physical-only and hybrid top-one winners agreed on 7/255 baseline targets and 8/255 expanded targets. These are algorithm consistency and rank-disagreement checks, not relevance or accuracy measures.
- Exact coordinate comparison found 74 expanded-top-five coordinates absent from baseline top fives. All 74 were returned by existing expanded Mars patch endpoints in the focused regression test. They are newly returned results, not proof of 74 newly acquired geographic sites.
- Regional `data/processed/ml/validation_report.json` reports a 15-site eligible Earth set and strong slope/roughness correlation. Its scoring and 60 km scale are separate from detailed retrieval.

## Unavailable validation and likely biases

No independent relevance labels or expert-reviewed positives/negatives exist. Therefore Recall@K, Precision@K, NDCG@K, Hit Rate@K and analog accuracy are unavailable. No controlled physical-only versus neural-only versus hybrid relevance comparison, shortlist recall study, rank stability perturbation study, or field validation is recorded. Model training uses Earth; Moon/Mars are out of domain. Elevation clipping can erase extreme relief, particularly for lunar terrain; report the per-target clipped fraction when available. Earth sampling is sparse and geographically biased. Source elevation quality, interpolated planetary grid cells, land-cover availability, and scale differences limit interpretation. Geological, atmospheric, radiation and operational suitability are not learned or scored.
