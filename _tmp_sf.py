import sys
sys.path.insert(0, '.')
from practice_studio import (
    practice_section_options,
    practice_section_type,
    practice_resolve_focus_section,
)

# User's example
sections = {
    "Verse 1": ["C", "G", "Am", "F"],
    "Chorus 1": ["F", "G", "C"],
    "Verse 2": ["C", "G", "Am", "F"],
    "Chorus 2": ["F", "G", "C"],
    "Bridge": ["Em", "F"],
    "Chorus 3": ["F", "G", "C"],
}

print('Section Focus options:', practice_section_options(sections))

# Selecting "Verse" -> resolve to first matching
for pick in ["Verse", "Chorus", "Bridge", "Full Song"]:
    resolved = practice_resolve_focus_section(pick, sections)
    print(f'  pick={pick!r:12s} -> resolved={resolved!r}')

# Piano Man-ish edge case
print()
print('Piano Man-ish (with Harmonica Solo 1 / 2):')
pm = {
    "Harmonica Intro": ["C"],
    "Verse 1": ["C", "G"],
    "Verse 2": ["C", "G"],
    "Chorus 1": ["F", "G"],
    "Harmonica Solo 1": ["C", "G"],
    "Verse 3A": ["C"],
    "Verse 3B": ["G"],
    "Harmonica Solo 2": ["C"],
    "Chorus 2": ["F"],
    "Bridge 1": ["Em"],
    "Bridge 2": ["Am"],
    "Final Harmonica Outro": ["G"],
}
print('Options:', practice_section_options(pm))
for pick in ["Verse", "Chorus", "Bridge", "Harmonica Solo", "Final Harmonica Outro"]:
    resolved = practice_resolve_focus_section(pick, pm)
    print(f'  pick={pick!r:25s} -> resolved={resolved!r}')
