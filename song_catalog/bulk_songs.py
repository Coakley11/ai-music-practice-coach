"""Generated practice charts for a large searchable library (simplified / generic forms)."""

from __future__ import annotations

from typing import Any

from music_theory import transpose_sections_dict


def _ext() -> dict[str, Any]:
    return {
        "midi_path": None,
        "musicxml_path": None,
        "harmonic_analysis": None,
        "arrangement_notes": "Auto-generated practice chart; refine with licensed sources later.",
    }


def _row(
    title: str,
    artist: str,
    genre: str,
    key: str,
    sections: dict[str, list[str]],
    composer: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "artist": artist,
        "genre": genre,
        "key": key,
        "sections": sections,
        "guitar_tabs": {},
        "composer": composer,
        "extensions": _ext(),
    }


def _tpl(ref_key: str, sections: dict[str, list[str]], target_key: str) -> dict[str, list[str]]:
    return transpose_sections_dict(sections, ref_key, target_key)


# --- Reusable harmonic shells (transposed to each song key) ---
_POP_IVVI = {
    "Verse": ["C", "G", "Am", "F"],
    "Chorus": ["F", "G", "C", "Am"],
    "Bridge": ["Dm7", "G", "C", "C"],
}

_POP_VI_IV = {
    "Verse": ["Am", "F", "C", "G"],
    "Chorus": ["C", "G", "Am", "F"],
    "Bridge": ["F", "Dm", "G", "C"],
}

_POP_SOFT = {
    "Verse": ["G", "Em", "C", "D"],
    "Chorus": ["C", "G", "D", "Em"],
    "Bridge": ["Em", "C", "G", "D"],
}

_ROCK_CLASSIC = {
    "Verse": ["E", "A", "E", "B"],
    "Chorus": ["A", "E", "B", "E"],
    "Bridge": ["C#m", "A", "E", "B"],
}

_ROCK_ACDC = {
    "Intro / Riff": ["A", "A", "D", "A"],
    "Verse": ["A", "A", "D", "A"],
    "Chorus": ["A", "D", "A", "E"],
}

_ROCK_GRUNGE = {
    "Verse": ["E", "G", "A", "C"],
    "Chorus": ["A", "C", "E", "E"],
    "Bridge": ["G", "D", "A", "E"],
}

_FUNK_ONE = {
    "Main Groove": ["Em7", "Em7", "Em7", "Em7"],
    "Breakdown": ["Am7", "B7", "Em7", "Em7"],
}

_FUNK_TWO = {
    "Vamp": ["Dm7", "G7", "Dm7", "G7"],
    "Lift": ["Fmaj7", "Em7", "Dm7", "G7"],
}

_BLUES_12 = {
    "Bars 1-4": ["A7", "D7", "A7", "A7"],
    "Bars 5-8": ["D7", "D7", "A7", "A7"],
    "Bars 9-12": ["E7", "D7", "A7", "E7"],
}

_JAZZ_BIRDBLUES = {
    "A Section": ["Fmaj7", "Em7b5", "A7", "Dm7", "Gm7", "C7", "Fmaj7", "Fmaj7"],
    "B Section": ["Dm7", "G7", "Cmaj7", "Cmaj7", "Am7", "D7", "Gm7", "C7"],
}

_JAZZ_MINOR_II_V = {
    "A Section": ["Dm7b5", "G7", "Cm7", "Cm7", "Fm7", "Bb7", "Ebmaj7", "Ebmaj7"],
    "B Section": ["Am7b5", "D7", "Gm7", "Gm7", "Cm7", "F7", "Bbmaj7", "Bbmaj7"],
}

_BOSSA_BASIC = {
    "A Section": ["Cmaj7", "Cmaj7", "Dm7", "G7", "Cmaj7", "Cmaj7", "Bm7b5", "E7"],
    "B Section": ["Am7", "D7", "Dm7", "G7", "Cmaj7", "A7", "Dm7", "G7"],
}

_CLASSICAL_SIMPLE = {
    "Theme": ["G", "D", "Em", "C", "G", "D", "G", "G"],
    "Variation": ["Em", "C", "G", "D"],
}


def _add_pop_pack(out: list, pairs: list[tuple[str, str, str, str]], tpl_name: str) -> None:
    tpl_map = {
        "ivvi": ("C", _POP_IVVI),
        "vi_iv": ("C", _POP_VI_IV),
        "soft": ("C", _POP_SOFT),
    }
    ref_key, sec = tpl_map[tpl_name]
    for title, artist, key, comp in pairs:
        out.append(_row(title, artist, "Pop", key, _tpl(ref_key, sec, key), composer=comp or None))


def _add_rock_pack(out: list, pairs: list[tuple[str, str, str, str]], kind: str) -> None:
    kinds = {
        "classic": ("E", _ROCK_CLASSIC),
        "ac": ("A", _ROCK_ACDC),
        "grunge": ("E", _ROCK_GRUNGE),
    }
    ref_key, sec = kinds[kind]
    for title, artist, key, comp in pairs:
        out.append(_row(title, artist, "Rock", key, _tpl(ref_key, sec, key), composer=comp or None))


def bulk_song_records() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    # --- Pop (iv–V–vi–IV and variants) ---
    pop_ivvi = [
        ("As It Was", "Harry Styles", "A", None),
        ("Watermelon Sugar", "Harry Styles", "D", None),
        ("Anti-Hero", "Taylor Swift", "E", None),
        ("Shake It Off", "Taylor Swift", "G", None),
        ("Blank Space", "Taylor Swift", "F", None),
        ("Levitating", "Dua Lipa", "Bm", None),
        ("Don't Start Now", "Dua Lipa", "Bm", None),
        ("Blinding Lights", "The Weeknd", "Dm", None),
        ("Save Your Tears", "The Weeknd", "C", None),
        ("Uptown Funk", "Mark Ronson ft. Bruno Mars", "D", None),
        ("Locked Out of Heaven", "Bruno Mars", "D", None),
        ("When I Was Your Man", "Bruno Mars", "C", None),
        ("Rolling in the Deep", "Adele", "Cm", None),
        ("Someone Like You", "Adele", "A", None),
        ("Easy On Me", "Adele", "F", None),
        ("Shallow", "Lady Gaga & Bradley Cooper", "Em", None),
        ("Poker Face", "Lady Gaga", "Em", None),
        ("Bad Romance", "Lady Gaga", "Am", None),
        ("Roar", "Katy Perry", "Bb", None),
        ("Firework", "Katy Perry", "Ab", None),
        ("Call Me Maybe", "Carly Rae Jepsen", "G", None),
        ("Happy", "Pharrell Williams", "F", None),
        ("Get Lucky", "Daft Punk", "Bm", None),
        ("Counting Stars", "OneRepublic", "Cm", None),
        ("Apologize", "OneRepublic", "Cm", None),
        ("Radioactive", "Imagine Dragons", "Bm", None),
        ("Demons", "Imagine Dragons", "D", None),
        ("Believer", "Imagine Dragons", "Bb", None),
        ("Someone You Loved", "Lewis Capaldi", "Db", None),
        ("Before You Go", "Lewis Capaldi", "F", None),
        ("Stay", "The Kid LAROI & Justin Bieber", "Am", None),
        ("Peaches", "Justin Bieber", "C", None),
        ("Ghost", "Justin Bieber", "D", None),
        ("Flowers", "Miley Cyrus", "Am", None),
        ("Wrecking Ball", "Miley Cyrus", "D", None),
        ("Drivers License", "Olivia Rodrigo", "Bb", None),
        ("Good 4 U", "Olivia Rodrigo", "A", None),
        ("Vampire", "Olivia Rodrigo", "F", None),
        ("Unholy", "Sam Smith & Kim Petras", "Em", None),
        ("Stay With Me", "Sam Smith", "Am", None),
        ("Latch", "Disclosure ft. Sam Smith", "Gm", None),
        ("Cold Heart", "Elton John & Dua Lipa", "F", None),
        ("Tiny Dancer", "Elton John", "C", "Elton John / Bernie Taupin"),
        ("Rocket Man", "Elton John", "Bb", "Elton John / Bernie Taupin"),
        ("Your Song", "Elton John", "Eb", "Elton John / Bernie Taupin"),
        ("Faith", "George Michael", "B", None),
        ("Careless Whisper", "George Michael", "Dm", None),
        ("Wake Me Up", "Avicii", "Bm", None),
        ("Levels", "Avicii", "C", None),
        ("Titanium", "David Guetta ft. Sia", "Cm", None),
        ("Without You", "David Guetta ft. Usher", "Gm", None),
    ]
    _add_pop_pack(out, pop_ivvi, "ivvi")

    pop_vi = [
        ("Lose Yourself", "Eminem", "Dm", None),
        ("Stan", "Eminem", "Dm", None),
        ("Numb", "Linkin Park", "F#m", None),
        ("In the End", "Linkin Park", "F#m", None),
        ("Crawling", "Linkin Park", "F#m", None),
        ("Bring Me to Life", "Evanescence", "Am", None),
        ("My Immortal", "Evanescence", "A", None),
        ("Zombie", "The Cranberries", "Em", None),
        ("Linger", "The Cranberries", "D", None),
        ("Wonderwall", "Oasis", "Em", None),
        ("Don't Look Back in Anger", "Oasis", "C", None),
        ("Champagne Supernova", "Oasis", "A", None),
        ("Mr. Brightside", "The Killers", "D", None),
        ("Somebody Told Me", "The Killers", "Ab", None),
        ("Human", "The Killers", "A", None),
        ("Clocks", "Coldplay", "Eb", None),
        ("The Scientist", "Coldplay", "F", None),
        ("Paradise", "Coldplay", "F", None),
    ]
    _add_pop_pack(out, pop_vi, "vi_iv")

    pop_soft = [
        ("Landslide", "Fleetwood Mac", "G", None),
        ("Dreams", "Fleetwood Mac", "F", None),
        ("Go Your Own Way", "Fleetwood Mac", "F", None),
        ("Hotel California", "Eagles", "Bm", "Don Felder / Don Henley / Glenn Frey"),
        ("Take It Easy", "Eagles", "G", "Jackson Browne / Glenn Frey"),
        ("Desperado", "Eagles", "G", "Glenn Frey / Don Henley"),
        ("Free Fallin'", "Tom Petty", "D", None),
        ("American Girl", "Tom Petty", "D", None),
        ("Learning to Fly", "Tom Petty", "F", None),
    ]
    _add_pop_pack(out, pop_soft, "soft")

    # --- Rock ---
    rock_c = [
        ("Sweet Child O' Mine", "Guns N' Roses", "Db", None),
        ("November Rain", "Guns N' Roses", "C", None),
        ("Paradise City", "Guns N' Roses", "F", None),
        ("Livin' on a Prayer", "Bon Jovi", "Em", None),
        ("You Give Love a Bad Name", "Bon Jovi", "A", None),
        ("Wanted Dead or Alive", "Bon Jovi", "D", None),
        ("Eye of the Tiger", "Survivor", "Cm", None),
        ("The Final Countdown", "Europe", "F#m", None),
        ("Carry On Wayward Son", "Kansas", "Am", None),
        ("Dust in the Wind", "Kansas", "C", None),
        ("More Than a Feeling", "Boston", "D", None),
        ("Peace of Mind", "Boston", "D", None),
        ("Foreplay / Long Time", "Boston", "C", None),
        ("Barracuda", "Heart", "F#", None),
        ("Magic Man", "Heart", "Am", None),
        ("Crazy on You", "Heart", "A", None),
        ("Rock and Roll All Nite", "KISS", "A", None),
        ("Detroit Rock City", "KISS", "A", None),
        ("Beth", "KISS", "C", None),
        ("Paint It Black", "The Rolling Stones", "Em", None),
        ("Satisfaction", "The Rolling Stones", "E", None),
        ("Jumpin' Jack Flash", "The Rolling Stones", "B", None),
        ("You Really Got Me", "The Kinks", "G", None),
        ("Lola", "The Kinks", "C", None),
        ("All Along the Watchtower", "Jimi Hendrix", "Cm", "Bob Dylan"),
        ("Purple Haze", "Jimi Hendrix", "E", None),
        ("Little Wing", "Jimi Hendrix", "F#", None),
        ("Wind Cries Mary", "Jimi Hendrix", "F", None),
        ("Smoke on the Water", "Deep Purple", "G", None),
        ("Highway Star", "Deep Purple", "G", None),
        ("Child in Time", "Deep Purple", "Gm", None),
        ("Carry On", "Crosby, Stills, Nash & Young", "D", None),
        ("Teach Your Children", "Crosby, Stills, Nash & Young", "D", None),
        ("Suite: Judy Blue Eyes", "Crosby, Stills & Nash", "G", None),
    ]
    _add_rock_pack(out, rock_c, "classic")

    rock_ac = [
        ("Back in Black", "AC/DC", "E", None),
        ("Highway to Hell", "AC/DC", "A", None),
        ("Thunderstruck", "AC/DC", "B", None),
        ("You Shook Me All Night Long", "AC/DC", "G", None),
        ("T.N.T.", "AC/DC", "E", None),
        ("Dirty Deeds Done Dirt Cheap", "AC/DC", "A", None),
        ("Whole Lotta Love", "Led Zeppelin", "E", None),
        ("Rock and Roll", "Led Zeppelin", "A", None),
        ("Black Dog", "Led Zeppelin", "A", None),
        ("Immigrant Song", "Led Zeppelin", "F#", None),
    ]
    _add_rock_pack(out, rock_ac, "ac")

    rock_grunge = [
        ("Smells Like Teen Spirit", "Nirvana", "F", None),
        ("Come as You Are", "Nirvana", "Em", None),
        ("Lithium", "Nirvana", "E", None),
        ("Black", "Pearl Jam", "E", None),
        ("Alive", "Pearl Jam", "A", None),
        ("Even Flow", "Pearl Jam", "E", None),
        ("Plush", "Stone Temple Pilots", "G", None),
        ("Interstate Love Song", "Stone Temple Pilots", "A", None),
        ("Vasoline", "Stone Temple Pilots", "E", None),
    ]
    _add_rock_pack(out, rock_grunge, "grunge")

    # --- Funk ---
    for title, artist, key in [
        ("Good Times", "Chic", "E"),
        ("Le Freak", "Chic", "Am"),
        ("Give Up the Funk", "Parliament", "Bb"),
        ("Flashlight", "Parliament", "Bb"),
        ("Brick House", "Commodores", "A"),
        ("Play That Funky Music", "Wild Cherry", "E"),
        ("Pick Up the Pieces", "Average White Band", "Dm"),
        ("Fire", "Ohio Players", "E"),
        ("Love Rollercoaster", "Ohio Players", "E"),
        ("Get Down Tonight", "KC and the Sunshine Band", "F"),
        ("Celebration", "Kool & the Gang", "Bb"),
        ("Jungle Boogie", "Kool & the Gang", "Am"),
        ("Ladies Night", "Kool & the Gang", "C"),
        ("September", "Earth, Wind & Fire", "F#m"),
        ("Shining Star", "Earth, Wind & Fire", "Eb"),
        ("Boogie Wonderland", "Earth, Wind & Fire", "Em"),
        ("Can't Hide Love", "Earth, Wind & Fire", "A"),
        ("I Wish", "Stevie Wonder", "Eb"),
        ("Higher Ground", "Stevie Wonder", "Eb"),
        ("Master Blaster", "Stevie Wonder", "B"),
        ("Rock with You", "Michael Jackson", "Em"),
        ("Billie Jean", "Michael Jackson", "F#m"),
        ("Don't Stop 'Til You Get Enough", "Michael Jackson", "F#m"),
        ("Get Up (I Feel Like Being a) Sex Machine", "James Brown", "A"),
        ("Cold Sweat", "James Brown", "D"),
        ("Papa's Got a Brand New Bag", "James Brown", "A"),
    ]:
        out.append(_row(title, artist, "Funk", key, _tpl("E", _FUNK_ONE, key)))

    for title, artist, key in [
        ("Thank You (Falettinme Be Mice Elf Agin)", "Sly and the Family Stone", "Bb"),
        ("Family Affair", "Sly and the Family Stone", "Bb"),
        ("Everyday People", "Sly and the Family Stone", "C"),
        ("Tell Me Something Good", "Rufus & Chaka Khan", "Dm"),
        ("Ain't Nobody", "Rufus & Chaka Khan", "Am"),
        ("Raspberry Beret", "Prince", "A"),
        ("Kiss", "Prince", "A"),
        ("1999", "Prince", "F#"),
    ]:
        out.append(_row(title, artist, "Funk", key, _tpl("D", _FUNK_TWO, key)))

    # --- Blues (12-bar shells in multiple keys) ---
    for title, artist, key in [
        ("Sweet Home Chicago", "Robert Johnson", "A"),
        ("Crossroads", "Cream", "A"),
        ("Pride and Joy", "Stevie Ray Vaughan", "A"),
        ("Texas Flood", "Stevie Ray Vaughan", "G"),
        ("The Thrill Is Gone", "B.B. King", "Bm"),
        ("Every Day I Have the Blues", "B.B. King", "Bb"),
        ("Born Under a Bad Sign", "Albert King", "C#"),
        ("Red House", "Jimi Hendrix", "B"),
        ("Key to the Highway", "Eric Clapton", "A"),
        ("Before You Accuse Me", "Eric Clapton", "E"),
        ("Stormy Monday", "T-Bone Walker", "G"),
        ("Roadhouse Blues", "The Doors", "E"),
        ("I'm Tore Down", "Freddie King", "F"),
        ("Going Down", "Freddie King", "D"),
        ("Hide Away", "Freddie King", "E"),
        ("Rock Me Baby", "B.B. King", "A"),
        ("Hoochie Coochie Man", "Muddy Waters", "A"),
        ("Mannish Boy", "Muddy Waters", "A"),
        ("Got My Mojo Working", "Muddy Waters", "A"),
        ("Boom Boom", "John Lee Hooker", "E"),
    ]:
        out.append(_row(title, artist, "Blues", key, _tpl("A", _BLUES_12, key)))

    # --- Jazz standards (bird blues / minor ii–V shells) ---
    jazz_titles_bird = [
        ("Billie's Bounce", "Charlie Parker"),
        ("Now's the Time", "Charlie Parker"),
        ("Yardbird Suite", "Charlie Parker"),
        ("Confirmation", "Charlie Parker"),
        ("Donna Lee", "Charlie Parker"),
        ("Anthropology", "Charlie Parker"),
        ("Ornithology", "Charlie Parker"),
        ("Scrapple from the Apple", "Charlie Parker"),
        ("Cool Blues", "Charlie Parker"),
        ("Chi Chi", "Charlie Parker"),
    ]
    for title, artist in jazz_titles_bird:
        out.append(_row(title, artist, "Jazz", "F", _tpl("F", _JAZZ_BIRDBLUES, "F"), composer=artist))

    jazz_minor = [
        ("Softly, as in a Morning Sunrise", "Romberg & Hammerstein"),
        ("Invitation", "Bronisław Kaper"),
        ("Alone Together", "Arthur Schwartz"),
        ("Angel Eyes", "Matt Dennis"),
        ("Black Orpheus", "Luiz Bonfá"),
        ("St. James Infirmary", "Traditional"),
        ("Nature Boy", "eden ahbez"),
    ]
    for title, composer in jazz_minor:
        out.append(
            _row(
                title,
                composer,
                "Jazz",
                "Cm",
                _tpl("Cm", _JAZZ_MINOR_II_V, "Cm"),
                composer=composer,
            )
        )

    more_standards = [
        ("Tune Up", "Miles Davis", "Eb", _JAZZ_BIRDBLUES, "F", "Miles Davis"),
        ("Four", "Miles Davis", "Eb", _JAZZ_BIRDBLUES, "F", "Miles Davis"),
        ("Solar", "Miles Davis", "C", _JAZZ_BIRDBLUES, "F", "Miles Davis"),
        ("Song for My Father", "Horace Silver", "F#m", _JAZZ_MINOR_II_V, "Cm", "Horace Silver"),
        ("Cantaloupe Island", "Herbie Hancock", "F", _POP_VI_IV, "C", "Herbie Hancock"),
        ("Watermelon Man", "Herbie Hancock", "F", _FUNK_ONE, "E", "Herbie Hancock"),
        ("Maiden Voyage", "Herbie Hancock", "D", _JAZZ_MINOR_II_V, "Cm", "Herbie Hancock"),
        ("Footprints", "Wayne Shorter", "C#m", _JAZZ_MINOR_II_V, "Cm", "Wayne Shorter"),
        ("Black Nile", "Wayne Shorter", "C", _JAZZ_BIRDBLUES, "F", "Wayne Shorter"),
        ("Speak No Evil", "Wayne Shorter", "C", _JAZZ_MINOR_II_V, "Cm", "Wayne Shorter"),
        ("Stolen Moments", "Oliver Nelson", "C", _JAZZ_BIRDBLUES, "F", "Oliver Nelson"),
        ("Sidewinder", "Lee Morgan", "C", _FUNK_TWO, "D", "Lee Morgan"),
        ("Ceora", "Lee Morgan", "Ab", _POP_SOFT, "C", "Lee Morgan"),
        ("Mercy, Mercy, Mercy", "Joe Zawinul", "Bb", _POP_IVVI, "C", "Joe Zawinul"),
        ("Work Song", "Nat Adderley", "F", _JAZZ_BIRDBLUES, "F", "Nat Adderley"),
        ("The Preacher", "Horace Silver", "F", _JAZZ_BIRDBLUES, "F", "Horace Silver"),
        ("Doxy", "Sonny Rollins", "Bb", _JAZZ_BIRDBLUES, "F", "Sonny Rollins"),
        ("Tenor Madness", "Sonny Rollins", "Bb", _JAZZ_BIRDBLUES, "F", "Sonny Rollins"),
        ("St. Thomas", "Sonny Rollins", "C", _JAZZ_BIRDBLUES, "F", "Sonny Rollins"),
        ("Oleo", "Sonny Rollins", "Bb", _JAZZ_BIRDBLUES, "F", "Sonny Rollins"),
        ("Straight, No Chaser", "Thelonious Monk", "F", _JAZZ_BIRDBLUES, "F", "Thelonious Monk"),
        ("Blue Monk", "Thelonious Monk", "Bb", _JAZZ_MINOR_II_V, "Cm", "Thelonious Monk"),
        ("Round Midnight", "Thelonious Monk", "Eb", _JAZZ_MINOR_II_V, "Cm", "Thelonious Monk"),
        ("Well You Needn't", "Thelonious Monk", "F", _JAZZ_BIRDBLUES, "F", "Thelonious Monk"),
        ("In Walked Bud", "Thelonious Monk", "Eb", _JAZZ_BIRDBLUES, "F", "Thelonious Monk"),
        ("Take Five", "Paul Desmond", "Eb", _JAZZ_MINOR_II_V, "Cm", "Paul Desmond"),
        ("A Night in Tunisia", "Dizzy Gillespie", "Dm", _JAZZ_MINOR_II_V, "Cm", "Dizzy Gillespie"),
        ("Groovin' High", "Dizzy Gillespie", "Eb", _JAZZ_BIRDBLUES, "F", "Dizzy Gillespie"),
        ("Salt Peanuts", "Dizzy Gillespie", "Bb", _JAZZ_BIRDBLUES, "F", "Dizzy Gillespie"),
        ("Lullaby of Birdland", "George Shearing", "F", _JAZZ_BIRDBLUES, "F", "George Shearing"),
        ("Cherokee", "Ray Noble", "Bb", _JAZZ_BIRDBLUES, "F", "Ray Noble"),
        ("Donna Lee", "Charlie Parker", "Ab", _JAZZ_BIRDBLUES, "F", "Charlie Parker"),
        ("How High the Moon", "Morgan Lewis", "G", _JAZZ_BIRDBLUES, "F", "Morgan Lewis"),
        ("Stella by Starlight", "Victor Young", "Bb", _JAZZ_MINOR_II_V, "Cm", "Victor Young"),
        ("My Funny Valentine", "Richard Rodgers", "Cm", _JAZZ_MINOR_II_V, "Cm", "Richard Rodgers"),
        ("The Nearness of You", "Hoagy Carmichael", "F", _POP_SOFT, "C", "Hoagy Carmichael"),
        ("Georgia on My Mind", "Hoagy Carmichael", "F", _POP_IVVI, "C", "Hoagy Carmichael"),
        ("Skylark", "Hoagy Carmichael", "Eb", _POP_IVVI, "C", "Hoagy Carmichael"),
        ("Star Eyes", "Gene de Paul", "Eb", _JAZZ_BIRDBLUES, "F", "Gene de Paul"),
        ("On Green Dolphin Street", "Bronisław Kaper", "C", _JAZZ_BIRDBLUES, "F", "Bronisław Kaper"),
        ("Recorda Me", "Joe Henderson", "Am", _JAZZ_MINOR_II_V, "Cm", "Joe Henderson"),
        ("Inner Urge", "Joe Henderson", "C#", _JAZZ_MINOR_II_V, "Cm", "Joe Henderson"),
        ("Mood Indigo", "Duke Ellington", "Ab", _JAZZ_MINOR_II_V, "Cm", "Duke Ellington"),
        ("In a Sentimental Mood", "Duke Ellington", "Bb", _JAZZ_MINOR_II_V, "Cm", "Duke Ellington"),
        ("Caravan", "Duke Ellington", "C", _JAZZ_MINOR_II_V, "Cm", "Duke Ellington"),
        ("Perdido", "Juan Tizol", "Bb", _JAZZ_BIRDBLUES, "F", "Juan Tizol"),
        ("Sophisticated Lady", "Duke Ellington", "Ab", _JAZZ_MINOR_II_V, "Cm", "Duke Ellington"),
        ("C Jam Blues", "Duke Ellington", "C", _JAZZ_BIRDBLUES, "F", "Duke Ellington"),
    ]
    seen = set()
    for title, artist, key, template, ref, comp in more_standards:
        dup = (title.lower(), artist.lower())
        if dup in seen:
            continue
        seen.add(dup)
        out.append(_row(title, artist, "Jazz", key, _tpl(ref, template, key), composer=comp))

    # --- Bossa / Jobim titles (extra shells; curated has detailed Jobim hits) ---
    bossa_extra = [
        ("Chega de Saudade", "Antonio Carlos Jobim"),
        ("Só Danço Samba", "Antonio Carlos Jobim"),
        ("Triste", "Antonio Carlos Jobim"),
        ("Fotografia", "Antonio Carlos Jobim"),
        ("O Grande Amor", "Antonio Carlos Jobim"),
        ("Dindi", "Antonio Carlos Jobim"),
        ("Once I Loved", "Antonio Carlos Jobim"),
        ("Useless Landscape", "Antonio Carlos Jobim"),
        ("Tide", "Antonio Carlos Jobim"),
        ("Surfboard", "Antonio Carlos Jobim"),
        ("Luiza", "Antonio Carlos Jobim"),
        ("Retrato em Branco e Preto", "Antonio Carlos Jobim"),
        ("O Boto", "Antonio Carlos Jobim"),
        ("Samba do Avião", "Antonio Carlos Jobim"),
        ("Sabiá", "Antonio Carlos Jobim"),
        ("Água de Meninos", "Antonio Carlos Jobim"),
        ("Garota de Ipanema", "Antonio Carlos Jobim"),
        ("Bonita", "Antonio Carlos Jobim"),
        ("Look to the Sky", "Antonio Carlos Jobim"),
        ("Two Kites", "Antonio Carlos Jobim"),
        ("Desafinado", "Antonio Carlos Jobim"),
        ("Corcovado", "Antonio Carlos Jobim"),
        ("Girl from Ipanema", "Antonio Carlos Jobim"),
        ("Insensatez", "Antonio Carlos Jobim"),
        ("Quiet Nights", "Antonio Carlos Jobim"),
        ("Ela é Carioca", "Antonio Carlos Jobim"),
        ("Amparo", "Antonio Carlos Jobim"),
        ("Captain Bacardi", "Antonio Carlos Jobim"),
        ("Chovendo na Roseira", "Antonio Carlos Jobim"),
        ("Valse", "Antonio Carlos Jobim"),
        ("Portrait in Black and White", "Antonio Carlos Jobim"),
    ]
    for title, artist in bossa_extra:
        out.append(_row(title, artist, "Jazz", "C", _tpl("C", _BOSSA_BASIC, "C"), composer=artist))

    # --- Classical (simple diatonic practice) ---
    classical = [
        ("Für Elise", "Beethoven", "Am", "Ludwig van Beethoven"),
        ("Moonlight Sonata (theme)", "Beethoven", "C#m", "Ludwig van Beethoven"),
        ("Symphony No. 5 (opening motif)", "Beethoven", "Cm", "Ludwig van Beethoven"),
        ("Minuet in G", "Bach", "G", "Johann Sebastian Bach"),
        ("Air on the G String", "Bach", "C", "Johann Sebastian Bach"),
        ("Jesu, Joy of Man's Desiring", "Bach", "G", "Johann Sebastian Bach"),
        ("Prelude in C (WTC I)", "Bach", "C", "Johann Sebastian Bach"),
        ("Canon in D (ground)", "Pachelbel", "D", "Johann Pachelbel"),
        ("Clair de Lune (opening)", "Debussy", "Db", "Claude Debussy"),
        ("Gymnopédie No. 1", "Satie", "D", "Erik Satie"),
        ("Morning Mood", "Grieg", "G", "Edvard Grieg"),
        ("In the Hall of the Mountain King", "Grieg", "Bm", "Edvard Grieg"),
        ("Eine kleine Nachtmusik (theme)", "Mozart", "G", "Wolfgang Amadeus Mozart"),
        ("Symphony No. 40 (theme)", "Mozart", "Gm", "Wolfgang Amadeus Mozart"),
        ("La donna è mobile (outline)", "Verdi", "G", "Giuseppe Verdi"),
        ("Nessun dorma (outline)", "Puccini", "G", "Giacomo Puccini"),
    ]
    for title, artist, key, comp in classical:
        out.append(_row(title, artist, "Classical", key, _tpl("G", _CLASSICAL_SIMPLE, key), composer=comp))

    more_pop_ivvi = [
        ("You're Beautiful", "James Blunt", "Eb", None),
        ("Goodbye My Lover", "James Blunt", "F", None),
        ("Chasing Cars", "Snow Patrol", "A", None),
        ("Run", "Snow Patrol", "C", None),
        ("Use Somebody", "Kings of Leon", "C", None),
        ("Sex on Fire", "Kings of Leon", "E", None),
        ("Notion", "Kings of Leon", "B", None),
        ("Ho Hey", "The Lumineers", "C", None),
        ("Stubborn Love", "The Lumineers", "G", None),
        ("Ophelia", "The Lumineers", "F", None),
        ("Riptide", "Vance Joy", "C", None),
        ("Mess Is Mine", "Vance Joy", "G", None),
        ("7 Years", "Lukas Graham", "Gm", None),
        ("Love Someone", "Lukas Graham", "F", None),
        ("Take Me to Church", "Hozier", "Em", None),
        ("From Eden", "Hozier", "Am", None),
        ("Cherry Wine", "Hozier", "G", None),
    ]
    _add_pop_pack(out, more_pop_ivvi, "ivvi")

    more_rock = [
        ("Panama", "Van Halen", "A", None),
        ("Jump", "Van Halen", "C", None),
        ("Hot for Teacher", "Van Halen", "A", None),
        ("Crazy Train", "Ozzy Osbourne", "F#m", None),
        ("Mr. Crowley", "Ozzy Osbourne", "Am", None),
        ("Bark at the Moon", "Ozzy Osbourne", "Em", None),
        ("Iron Man", "Black Sabbath", "Em", None),
        ("Paranoid", "Black Sabbath", "E", None),
        ("War Pigs", "Black Sabbath", "E", None),
        ("Enter Sandman", "Metallica", "Em", None),
        ("Nothing Else Matters", "Metallica", "Em", None),
        ("Master of Puppets", "Metallica", "Em", None),
        ("Welcome to the Jungle", "Guns N' Roses", "Eb", None),
        ("Knockin' on Heaven's Door", "Guns N' Roses", "G", None),
        ("You Could Be Mine", "Guns N' Roses", "E", None),
        ("Runnin' with the Devil", "Van Halen", "A", None),
        ("American Idiot", "Green Day", "Ab", None),
        ("Basket Case", "Green Day", "Eb", None),
        ("When I Come Around", "Green Day", "G", None),
        ("Boulevard of Broken Dreams", "Green Day", "Fm", None),
        ("Holiday", "Green Day", "F", None),
        ("Californication", "Red Hot Chili Peppers", "Am", None),
        ("Under the Bridge", "Red Hot Chili Peppers", "E", None),
        ("Scar Tissue", "Red Hot Chili Peppers", "F", None),
        ("Snow (Hey Oh)", "Red Hot Chili Peppers", "B", None),
        ("Can't Stop", "Red Hot Chili Peppers", "E", None),
        ("Seven Nation Army", "The White Stripes", "E", None),
        ("Fell in Love with a Girl", "The White Stripes", "B", None),
        ("Icky Thump", "The White Stripes", "E", None),
    ]
    _add_rock_pack(out, more_rock, "classic")

    return out
