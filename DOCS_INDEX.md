# 📚 Documentation Index

This directory contains guides to help with implementing the Run Registry feature for the Project Paradise Backtester.

## Documents

### 1. **PATRICK_START_HERE.md** ⭐ Start Here!
Quick answer to Patrick's immediate questions:
- Do I need to make a new folder?
- Is there baseline in place?
- Where should I start?

**Read this first** for a quick orientation (5 min read).

### 2. **RUN_REGISTRY_GUIDE.md** 📖 Complete Guide
Comprehensive implementation guide with:
- Current state analysis (what exists, what's missing)
- Recommended architecture and file structure
- Complete code examples for all components
- Usage examples and patterns
- Integration strategies
- Development workflow and time estimates

**Read this** when you're ready to start implementing (20 min read).

## Quick Summary

**Question:** Where do I start with the run registry feature?

**Answer:** 
1. Create new folder: `vectorbt/portfolio/registry/`
2. No baseline exists yet - this is a new feature
3. You CAN leverage existing infrastructure (Portfolio serialization, Records)
4. Estimated implementation: 6-8 hours

## Files You'll Create

```
vectorbt/portfolio/registry/
├── __init__.py              # Package exports
├── run.py                   # RunRecord dataclass
├── registry.py              # RunRegistry main interface
└── stores/
    ├── __init__.py
    └── file_store.py        # File-based storage backend
```

## What is a Run Registry?

A **Run Registry** is a system that tracks and manages backtest runs, allowing users to:
- 💾 Save backtest results with metadata (strategy name, parameters, tags)
- 📋 List and filter past runs
- 🔍 Compare multiple runs side-by-side
- 📊 Find best-performing configurations
- 🔄 Reload old portfolios for analysis

Think of it as a "database" or "history" for all your backtests, instead of running them and losing the results when your Python session ends.

## Why This Matters

As Lev said:
> "Run registry would be awesome to be honest, i think that's something that's really missing from many backtesters"

Most backtesting tools let you run tests but don't provide a systematic way to track and compare results over time. This feature fills that gap!

## Need Help?

- Questions about the architecture? → See RUN_REGISTRY_GUIDE.md "Recommended Implementation Plan"
- Not sure what exists already? → See RUN_REGISTRY_GUIDE.md "Current State of the Repository"
- Want to see usage examples? → See RUN_REGISTRY_GUIDE.md "Usage Examples"
- Just want to get started? → Read PATRICK_START_HERE.md

---

Happy coding! 🚀
