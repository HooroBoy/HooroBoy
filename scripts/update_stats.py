#!/usr/bin/env python3
"""Refresh assets/stats.svg only.

Runs in GitHub Actions (see .github/workflows/update-stats.yml). The full
build (scripts/build_readme.py) also needs the portfolio source images, which
are not in this repo — that one is meant to be run locally.
"""
import build_readme as B

if __name__ == "__main__":
    B.build_stats()
