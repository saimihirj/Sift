# Legacy — Google Cloud / Firebase Deployment

These files were the GCP/Firebase production deployment for Sift (project `sift-495116`).

They are archived here for reference. The active platform now runs **localhost-first** with Render as the recommended shared deployment.

## Archived files

- `.firebaserc` — Firebase project config
- `firebase.json` — Firebase Hosting rewrites
- `cloudbuild.yaml` — Cloud Build → Cloud Run pipeline
- `tools/configure_oauth_cloud_run.sh` — OAuth secrets push to Cloud Run
- `tools/deploy_clean_webapp_link.sh` — Firebase Hosting link deploy
- `tools/deploy_gcp_fresh.sh` — Full GCP fresh deploy
- `tools/push_public_launch.sh` — Public launch push
- `docs/GCP_SERVERLESS_DEPLOYMENT.md` — Full GCP deployment guide
- `docs/DEPLOYMENT_CHECKLIST.md` — GCP deployment checklist

## Restoring GCP deployment

If you want to restore GCP deployment:

1. Move files back to project root and `tools/` and `docs/`
2. Install GCP dependencies: `pip install -r requirements-gcp.txt`
3. Set GCP environment variables in `.env`
4. Follow `docs/GCP_SERVERLESS_DEPLOYMENT.md`
