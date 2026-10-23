# Hackathon: The Shifters

> Built at **Epitech Rennes** · B-TBM-100 · Product Design Hackathon · January 2026

## Overview

Web application built during a hackathon for the **The Shifters** association. Search for a city and get its environmental score, computed from open data (air quality, mobility...). The goal: give the association concrete material to convince local authorities, based on real examples.

## Features

- City search and environmental score
- Python backend aggregating open data APIs (OpenAQ, mobility)
- HTML / CSS / JavaScript frontend with detailed modal cards
- Scoring criteria documented in `criteres et api.md`

## Tech stack

`Python` · `FastAPI / Uvicorn` · `JavaScript` · `HTML / CSS` · `OpenAQ API`

## Configuration

The backend needs an OpenAQ API key in the `OPENAQ_API_KEY` environment variable.

No secret is committed: create your own local `.env` file.

---

## Technical documentation

### Commit Convention
```
Format of the commit message: KARMA GIT

  <type>(<scope>): <subject>
  <BLANK LINE>
  <body>

USEFUL <type> : 
  [FEAT] #For adding a new "feature" for the user.
  [FIX] #For fixing a "feature" relevant to the user.
  [RM] #For removing a "feature" relevant to the user.
  [REFACTOR] #For refactoring production code, e.g. renaming a variable.
  [DOCS] #For changes to the documentation/.md etc.
  [BUILD] #For updating build configuration, development tools or other changes irrelevant to the user.
  [TEST] #For adding missing tests, refactoring tests; no production code change.

USEFUL <scope>:
  - Init
  - Documentation (.md)
  - Deployment
  - Code development
  - Figma

```

---

More of my work on my [portfolio](https://charly-2025.github.io/myPortfolio/).
