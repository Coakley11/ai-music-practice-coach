"""Quick verification for Piano Man, Rocket Man, Billie Jean charts."""
from __future__ import annotations

from song_catalog.curated_songs import curated_song_records
from music_theory import transpose_sections


def sections_for_level(song_data, level):
    explicit_versions = song_data.get("chart_versions") or {}
    if level in explicit_versions and explicit_versions[level]:
        return explicit_versions[level]
    return song_data.get("sections", {})


def main() -> None:
    targets = [
        ("Piano Man", "Billy Joel"),
        ("Rocket Man", "Elton John"),
        ("Billie Jean", "Michael Jackson"),
    ]
    records = {(r["title"], r["artist"]): r for r in curated_song_records()}
    for key in targets:
        r = records[key]
        print("=" * 60)
        print(
            f"{r['title']} / {r['artist']}  key={r['key']}  status={r.get('chart_status')}"
        )
        for level in ["Beginner", "Intermediate", "Advanced"]:
            sec = sections_for_level(r, level)
            total = sum(len(v) for v in sec.values())
            print(f"  {level}: {len(sec)} sections, {total} bars")
            for name, chords in sec.items():
                preview = " | ".join(chords[:8])
                suffix = " ..." if len(chords) > 8 else ""
                print(f"    {name} ({len(chords)}): {preview}{suffix}")
            if level == "Advanced":
                inter = sections_for_level(r, "Intermediate")
                if sec != inter:
                    print("    [Advanced differs from Intermediate]")
                else:
                    print("    [WARNING: Advanced equals Intermediate]")
        transposed = transpose_sections(
            {**r, "sections": sections_for_level(r, "Intermediate")}, "D"
        )
        verse = transposed.get("Verse") or transposed.get("Verse 1") or []
        print(f"  transpose to D (verse sample): {verse[:4]}")
        print(f"  lyric_cues: {list((r.get('lyric_cues') or {}).keys())}")


if __name__ == "__main__":
    main()
