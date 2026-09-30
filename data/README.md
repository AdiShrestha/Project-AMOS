# Data boundary

`quarantine/raw/` contains local candidate raw files copied from the user's legacy folder. They are ignored by Git and are not admitted inputs. Local identity is recorded in `project/candidate_data.json`; hashes establish which bytes were inspected, not acquisition authenticity or use/redistribution rights.

The legacy generated replays, synthetic replay, oracle scores and model weights are excluded. Production accepted/derived directories are intentionally absent until the admission and lineage contracts are implemented. Do not freeze the whole `data/` directory with quarantine inside it: use an explicitly reviewed accepted-data freeze scope and manifests after admission.
