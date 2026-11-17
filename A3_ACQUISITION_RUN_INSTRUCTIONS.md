# Running the A3 e-Stat acquisition workflow

The acquisition workflow is manual and does not commit raw data to Git.

## One-time setup

1. Register/log in at e-Stat and obtain an API application ID (appId). Official documentation: https://www.e-stat.go.jp/api/api-info/e-stat-manual3-0
2. In this GitHub repository, open Settings → Secrets and variables → Actions.
3. Create a repository secret named ESTAT_APP_ID and paste the application ID into its value. Do not put the ID in source code, issues, or chat messages.
4. Open Actions → e-Stat A3 mortality acquisition and audit → Run workflow.

## Expected artifact

The workflow should upload an artifact named estat-a3-mortality-<run_id> for 14 days. It contains:
- unchanged e-Stat metadata JSON
- unchanged monthly-data API JSON
- unchanged annual-total API JSON
- normalized 48-row CSV for 2020–2023
- annual reconciliation audit JSON and Markdown
- SHA256SUMS.txt

The script stops if any month is missing/duplicated/non-numeric or if monthly sums do not match both the e-Stat annual total and the official MHLW annual-report total. A failed run must be investigated; do not edit source values to force a pass.

No old MASTER or legacy derived data are read.
