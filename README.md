# Daily Briefing AI Agent

An AI agent that aggregates daily newsletters, research papers, and news articles, compiles them into a concise briefing, and integrates with Alexa to read it out every morning.

## Overview

This project fetches the latest content from:

- **Arxiv** (AI/ML research papers)  
- **Hacker News** (top tech stories)  
- **Custom RSS Feeds** (e.g., Zen Habits, Morning Brew)  

It then **summarizes** the content using a transformer (e.g., BART), **formats** it into an HTML briefing, **emails** it to you, and optionally makes it available to Amazon Alexa so you can get a spoken briefing each morning.

## Features

1. **Multi-Source Aggregation**  
2. **AI Summarization**  
3. **HTML Email Generation**  
4. **Alexa Integration**  

## Installation

1. **Clone this repo** or download the files.
2. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt

---

## 5. `LICENSE`

An example MIT License (replace as needed):

```plaintext
MIT License

Copyright (c) 2025 ...

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell...
