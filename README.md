# Daniel Cohen AI MUSIC PRACTICE COACH — v19

<!-- dev branch: Streamlit Cloud indexing refresh -->

**Development:** work on branch `dev`, push to `origin/dev` (Streamlit Cloud dev app). See [docs/DEV_WORKFLOW.md](docs/DEV_WORKFLOW.md). Run `.\scripts\setup-dev-git.ps1` once per clone.

**Roadmap & planning:** [cursor-prompts/music_app_roadmap.md](cursor-prompts/music_app_roadmap.md) (tasks, backlog, and completed features in the same folder).

The Adaptive Practice Sheet Generator is now fitted to the actual song context.

It uses:
1. Uploaded MIDI/MusicXML analysis
2. Selected public-domain song
3. Selected song-search/catalog song
4. Fallback practice progression

The adaptive sheet now includes:
- song title/source
- key
- sections
- full chord chart
- extracted melody notes when available
- instrument-specific exercises
- level-specific exercises
- song-specific transitions and chord loops
