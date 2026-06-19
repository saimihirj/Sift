# Sift v0.5.0 Demo Guide

Welcome to the Sift v0.5.0 POC. This guide outlines how to demonstrate the new intelligent decision layer features: **Neural Engine Tuning** and the **Dynamic Knowledge Graph Pipeline**.

## 1. Startup and Verification

1. Start the platform by running:
   ```bash
   npm run mvp
   ```
2. Verify the backend logs immediately upon startup. You should see the **Knowledge Daemon** initializing and executing its first domain scrape in the background.

## 2. Dynamic Knowledge Graph Pipeline

The platform is now continuously pulling state-of-the-art information across our target domains without blocking the main platform experience.

**To demo this:**
1. Open the UI and look at the **Sift Brain** panel (bottom left sidebar).
2. The domain freshness indicators (e.g., "SaaS", "Fintech") will display the exact timestamp and card count for newly ingested intelligence.
3. Behind the scenes, the daemon automatically updates the ChromaDB vector index and rebuilds the Entity-Relationship Knowledge Graph every time new intel is fetched. You can observe the terminal logs indicating `[updater] X new cards found` and `Re-indexing ChromaDB`.

## 3. Neural Engine Tuning Interface

You can now adjust weights and hyper-parameters directly from the Sift application, building your own custom local models on the fly.

**To demo this:**
1. In the **Sift Brain** panel, toggle **Tuning Mode**.
2. Explain the exposed parameters:
   - **LoRA Rank**: Controls the capacity of the low-rank adaptation (e.g., 8 for quick targeted fixes, 64 for deeper behavioral shifts).
   - **Learning Rate**: Controls the step size during gradient descent.
   - **Epochs**: Controls how many passes the engine takes over the newly ingested knowledge graph data.
3. Adjust the sliders to an aggressive configuration (e.g., Rank 64, Epochs 5).
4. Click **Start Fine-Tuning Job**.
5. Observe the live status stream below the button. The panel polls the backend (`/api/brain/tune/status`) and streams progress back to the user seamlessly.

## 4. Closing the Demo

Highlight the underlying philosophy: Sift is not just a UI wrapper over an open-source model. It is an **active, self-updating neural engine**. It continuously reads the web, ingests structured knowledge, and provides a low-latency interface to tune its own core weights based on that knowledge.

> "Nothing fancy, pure first-principle, logical, ambitious mindset."
