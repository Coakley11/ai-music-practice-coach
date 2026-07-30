"""Masterclass performance profiles for flagship catalog songs.

Each profile is private-lesson notes for one song — not interchangeable templates.
Authoring standard: ``cursor-prompts/plans/2026-07-29-flagship-coaching-quality-standard.md``

Every journey step should weave three questions:
  1. What is happening musically?
  2. How should I play it?
  3. What should I be feeling and listening for?

Explain *why*, not only *what*. Give each song its own voice.

Phase 1 framework complete — content-only work from here.
Review checklist: cursor-prompts/plans/2026-07-29-flagship-coaching-quality-standard.md
"""

from __future__ import annotations

from typing import Any

PerformanceProfile = dict[str, Any]

# Shared helpers for profile authors — section roles used in lesson journeys.
ROLE_INTRO = "_role:intro"
ROLE_VERSE = "_role:verse"
ROLE_CHORUS = "_role:chorus"
ROLE_PRE = "_role:pre"
ROLE_BRIDGE = "_role:bridge"
ROLE_INSTRUMENTAL = "_role:instrumental"
ROLE_OUTRO = "_role:outro"

CURATED_PERFORMANCE: dict[str, PerformanceProfile] = {
    "californiadreamin": {
        "title": "California Dreamin'",
        "interpretation": {
            "emotional_character": (
                "Grey-sky longing. The singer is cold, restless, and reaching toward a warmer "
                "place they can only imagine—the music should feel like a daydream, not a march."
            ),
            "listen_for": (
                "The vocal line hovering above walking bass motion, and the way suspended G# chords "
                " hesitate before they settle. If you hear hurry, you've lost the spell."
            ),
            "build_where": (
                "Let intensity bloom only in the instrumental break and the final verse return—"
                "everything else stays inward."
            ),
            "relax_where": (
                "Verses one and two, and the long fade on G#sus4 in the outro. "
                "Softness is the default mood."
            ),
            "accompaniment": (
                "Stay in the background in the verses—you are framing a voice. "
                "The instrumental may step forward briefly, then withdraw again."
            ),
            "rush_prone": (
                "The quick half-bar bass steps in every verse—players often clip them "
                "when the lyric feels urgent. Slow practice wins here."
            ),
            "key_transitions": (
                "The turn into the instrumental (after the long C# minor vamp), "
                "and the sus-to-minor landing at the very end."
            ),
            "master_challenge": (
                "Making the quick harmonic motion feel lazy and unhurried while the melody "
                "still floats. Rush the changes and the song becomes folk-rock filler; "
                "patience makes it iconic."
            ),
        },
        "practice_focus": {
            "Beginner": {"general": "Grey-sky daydream · unhurried verse hops · sus outro fade"},
            "Intermediate": {"general": "Floating vocal line · instrumental bloom · delayed resolution"},
            "Advanced": {"general": "Folk legato color · narrative arc · whispered final cadence"},
        },
        "lessons": {
            "Intermediate": {
                "piano": {
                    "opening": (
                        "When I teach California Dreamin', I ask students to picture a window "
                        "frosted over before they play a note. Your job is not to impress anyone "
                        "with harmony—you are setting up a memory of warmth that hasn't arrived yet."
                    ),
                    "journey": [
                        {
                            "role": ROLE_INTRO,
                            "heading": "Opening the window",
                            "body": (
                                "The intro is three bars of C# minor and a suspended lift—nothing more. "
                                "Roll the left-hand pattern slowly; resist filling the space. You are "
                                "establishing loneliness, not technique. The G#sus4 on the last bar "
                                "should feel like a question the verse will answer."
                            ),
                        },
                        {
                            "role": ROLE_VERSE,
                            "heading": "The walking daydream",
                            "body": (
                                "Here the verse has a gentle, flowing feel. Keep your left hand simple "
                                "with single bass notes that step C#m–B–A–B; let your right hand play "
                                "soft, connected chords. Do not rush the changes—the melody should always "
                                "feel like it's floating over your accompaniment. If your hands lock to "
                                "the beat, the singer will sound pinned down."
                            ),
                        },
                        {
                            "role": ROLE_INSTRUMENTAL,
                            "heading": "The break that remembers summer",
                            "body": (
                                "The long C# minor stretch is not filler—it is the daydream deepening. "
                                "Treat each repeat as slightly more inward, then allow a modest bloom "
                                "into the A–E–G#7 flick. This is the one place the band may swell, but "
                                "only for a breath before the sus figure pulls you back to winter."
                            ),
                        },
                        {
                            "role": ROLE_OUTRO,
                            "heading": "Letting the dream dissolve",
                            "body": (
                                "The outro refuses to end on a bang. Lean into G#sus4 for the full "
                                "four bars—half-pedal so the cloud stays luminous—then whisper the final "
                                "C#m as if you're closing the window you opened at the start."
                            ),
                        },
                    ],
                    "closing": (
                        "Play the song once start to finish thinking about temperature: cold intro, "
                        "slightly warmer instrumental, then cold again at the fade. That arc is the lesson."
                    ),
                },
                "guitar": {
                    "opening": (
                        "California Dreamin' is not a strumming workout. I tell guitarists to imagine "
                        "they're accompanying someone singing on a porch in November—your sound should "
                        "disappear the moment the lyric needs air."
                    ),
                    "journey": [
                        {
                            "role": ROLE_INTRO,
                            "heading": "Sparse beginnings",
                            "body": (
                                "Pick or brush C#m with space between strokes. The intro sets tempo and "
                                "mood; don't establish yourself as the lead voice yet."
                            ),
                        },
                        {
                            "role": ROLE_VERSE,
                            "heading": "Supporting, not competing",
                            "body": (
                                "This song isn't driven by aggressive strumming. Keep your wrist relaxed "
                                "and use a light, even pattern that supports the vocals rather than "
                                "competing with them. The half-bar hops will tempt you to rush—practice "
                                "them as a bass walk you could hum slowly."
                            ),
                        },
                        {
                            "role": ROLE_INSTRUMENTAL,
                            "heading": "Hypnotic, then alert",
                            "body": (
                                "Let the C#m vamp hypnotize. When the E–G#7 turn arrives, treat it as "
                                "a brief alertness in the dream—the only moment your right hand should "
                                "feel decisive."
                            ),
                        },
                        {
                            "role": ROLE_OUTRO,
                            "heading": "Dissolve, don't declare",
                            "body": (
                                "Widen the G#sus4 strum gradually, then soften bar by bar. The listener "
                                "should feel the song walk away, not end."
                            ),
                        },
                    ],
                    "closing": (
                        "Record yourself with no vocal and ask: would this guitar part bother a singer? "
                        "If yes, lighten again."
                    ),
                },
                "saxophone": {
                    "opening": (
                        "On sax, this tune belongs to the vocal—your tone should sound like someone "
                        "remembering a melody, not showcasing technique."
                    ),
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Shadow the singer",
                            "body": (
                                "If you play the verse melody, stay behind the imagined vocal in volume. "
                                "Short, rounded articulation; no vibrato showmanship yet."
                            ),
                        },
                        {
                            "role": ROLE_INSTRUMENTAL,
                            "heading": "Sing through the horn",
                            "body": (
                                "Imagine you're singing the melody. Take full breaths before each phrase, "
                                "connect the notes naturally, and gradually build your volume where the "
                                "line becomes more expressive—then relax again before the final verse returns."
                            ),
                        },
                        {
                            "role": ROLE_OUTRO,
                            "heading": "Release into silence",
                            "body": (
                                "Long tones on the sus resolution; diminuendo through the final C#m. "
                                "End with air, not a punch."
                            ),
                        },
                    ],
                    "closing": "If it feels like a solo, back off. If it feels like a memory, you're there.",
                },
            },
            "Beginner": {
                "piano": {
                    "card_summary": (
                        "Start with one goal: make the song feel sad and gentle. Fancy chords can wait. "
                        "Keep your accompaniment soft, let the melody float above it, and don't rush the "
                        "chord changes. If the music feels like a quiet daydream, you're playing it the "
                        "right way."
                    ),
                    "challenge_summary": (
                        "Keep the quick chord changes smooth and unhurried—the melody should float, not rush."
                    ),
                    "harmony_summary": (
                        "Listen for the gentle pull of suspended chords before they resolve."
                    ),
                    "opening": (
                        "Start with one goal: make the song feel sad and gentle. Fancy chords can wait."
                    ),
                    "coach_context": (
                        "This song is a grey-sky daydream—not a march. Listen for the melody floating "
                        "above simple chords, and stay soft until the music itself asks for more."
                    ),
                    "journey": [
                        {
                            "section": "Intro",
                            "role": ROLE_INTRO,
                            "heading": "Set the mood",
                            "body": (
                                "Before the verse begins, play the opening chords slowly and leave space "
                                "between them. You're setting up a lonely, winter feeling—not showing off. "
                                "If it sounds quiet and a little sad, you've got it."
                            ),
                        },
                        {
                            "section": "Verse 1",
                            "role": ROLE_VERSE,
                            "heading": "Learn the pattern",
                            "body": (
                                "The verse moves with a gentle, daydreaming feel. Your left hand steps "
                                "through one bass note at a time; your right hand holds soft chords that "
                                "connect smoothly. Focus on learning the pattern calmly—don't worry about "
                                "speed yet."
                            ),
                        },
                        {
                            "section": "Verse 2",
                            "role": ROLE_VERSE,
                            "heading": "Relax into the groove",
                            "body": (
                                "Same chords as before—now let your hands relax. Don't rush the changes; "
                                "listen for the melody floating above you, and keep your touch light enough "
                                "that the story stays intimate."
                            ),
                        },
                        {
                            "section": "Instrumental",
                            "role": ROLE_INSTRUMENTAL,
                            "heading": "A little more light",
                            "body": (
                                "As the instrumental begins, keep the same gentle pulse you've been using. "
                                "Let the music grow a little louder, but don't lose the calm feeling that "
                                "makes this song special."
                            ),
                        },
                        {
                            "section": "Verse 3",
                            "role": ROLE_VERSE,
                            "heading": "Let the feeling deepen",
                            "body": (
                                "The last verse is your chance to let a little more emotion in—not by "
                                "playing louder, but by allowing the melody to breathe before the song "
                                "fades away."
                            ),
                        },
                        {
                            "section": "Outro",
                            "role": ROLE_OUTRO,
                            "heading": "Hold the last cloud",
                            "body": (
                                "When you reach the suspended chords at the end, let them ring and get "
                                "softer bar by bar. The song should feel like it's walking away into "
                                "the distance."
                            ),
                        },
                    ],
                    "closing": "Slow and soft beats fast and correct at this stage.",
                },
                "guitar": {
                    "opening": "Think winter porch, not campfire singalong.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Light touch",
                            "body": (
                                "The verse feels reflective and unhurried—keep your strumming in the "
                                "background so the vocal line feels intimate and personal. Use a light "
                                "down-up pattern and change chords on time even if you only strum once "
                                "per bar; listen for how the harmony gently supports the melody rather "
                                "than competing with it."
                            ),
                        },
                    ],
                    "closing": "When in doubt, play less.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: (
                "Hear the bass walk under the tune—not a chord chart exercise, a small story in the lower register."
            ),
            ROLE_INSTRUMENTAL: (
                "The long minor vamp is anticipation; the tiny turnaround is the only jolt before color returns."
            ),
            ROLE_OUTRO: (
                "Suspension asks a question; the final minor answer should feel inevitable, not sudden."
            ),
        },
    },
    "perfect": {
        "title": "Perfect",
        "interpretation": {
            "emotional_character": (
                "Private devotion—a slow-dance confession between two people, not a stadium anthem."
            ),
            "listen_for": "Ring and space. The loop should shimmer; silence between phrases is part of the arrangement.",
            "build_where": "Each chorus opens the chest a little wider; the last chorus may feel like an embrace.",
            "relax_where": "Verses and intro—never loud early.",
            "accompaniment": "Background canvas that glows brighter when the melody asks.",
            "rush_prone": "The fingerpicked pattern—players add notes when nervous and kill the intimacy.",
            "key_transitions": "Verse to chorus: widen harmony without pushing tempo.",
            "master_challenge": "Sustain emotion through repetition without adding clutter.",
        },
        "practice_focus": {
            "Intermediate": {"general": "Shimmering loop · verse intimacy · chorus glow without volume"},
        },
        "lessons": {
            "Intermediate": {
                "piano": {
                    "opening": (
                        "Perfect is a wedding slow-dance in a small room. If your playing fills every "
                        "beat, you steal the intimacy the lyric needs."
                    ),
                    "journey": [
                        {
                            "role": ROLE_INTRO,
                            "heading": "The loop begins",
                            "body": (
                                "Establish the pattern once, softly—whole-note root, broken chord answer. "
                                "You're teaching the listener what 'home' sounds like."
                            ),
                        },
                        {
                            "role": ROLE_VERSE,
                            "heading": "Conversation, not performance",
                            "body": (
                                "Roll gentle broken chords. Let beats 2 and 3 carry a little more weight "
                                "than 1 and 4. You're accompanying a whispered promise."
                            ),
                        },
                        {
                            "role": ROLE_CHORUS,
                            "heading": "The embrace",
                            "body": (
                                "Widen to fuller chords but keep the same pulse—the lift is harmonic openness, "
                                "not louder hitting. Imagine arms around someone, not hands in the air."
                            ),
                        },
                        {
                            "role": ROLE_OUTRO,
                            "heading": "Return to the loop",
                            "body": (
                                "Strip back to the intro pattern and let the ring decay naturally. "
                                "The song ends in tenderness, not triumph."
                            ),
                        },
                    ],
                    "closing": "Record at whisper volume. If it still feels sweet, you've understood it.",
                },
                "guitar": {
                    "opening": "Your thumb sets the heartbeat; the melody lives in the ring of the high strings.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Fingerpick the promise",
                            "body": (
                                "Accent the bass on beat 1; let treble notes bleed into beat 2. "
                                "No percussive slaps—the vocal carries the emotion."
                            ),
                        },
                        {
                            "role": ROLE_CHORUS,
                            "heading": "Slightly fuller, same heartbeat",
                            "body": (
                                "Stronger thumb, same pattern. Think 'embrace' not 'arena strum.'"
                            ),
                        },
                    ],
                    "closing": "When the pattern feels boring, you're probably close to the record.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: "The loop is a lullaby—protect the spaces.",
            ROLE_CHORUS: "Harmony opens like a smile; tempo stays constant.",
        },
    },
    "shallow": {
        "title": "Shallow",
        "interpretation": {
            "emotional_character": (
                "Vulnerable dialogue—two people deciding whether to leap, afraid and hopeful at once."
            ),
            "listen_for": "The 6/8 lilt and the moment the melody dares to climb in the chorus.",
            "build_where": "Chorus and final climbs—one honest peak, not constant belt.",
            "relax_where": "Verses and pre-chorus setup—stay close-mic'd in your imagination.",
            "accompaniment": "Transparent; you should hear the lyric through the chords.",
            "rush_prone": "Rushing the 6/8 feel when excitement builds.",
            "key_transitions": "Pre-chorus into chorus—the band widens but shouldn't cover the voice.",
            "master_challenge": "Intimacy first; power only when the lyric earns it.",
        },
        "practice_focus": {
            "Intermediate": {"general": "6/8 dialogue · verse whisper · one earned chorus peak"},
        },
        "lessons": {
            "Intermediate": {
                "piano": {
                    "opening": (
                        "Shallow is a duet in a kitchen, not a finale on a talent show. Listen more than you play."
                    ),
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Speech in 6/8",
                            "body": (
                                "Arpeggiate with the lyric syllables—right hand follows speech rhythm. "
                                "Pedal lightly; imagine one microphone for both singer and piano."
                            ),
                        },
                        {
                            "role": ROLE_CHORUS,
                            "heading": "The leap",
                            "body": (
                                "Open voicings when the melody jumps, but don't hammer. Sustained vowels "
                                "need room to soar; your job is to widen the river, not push the boat."
                            ),
                        },
                    ],
                    "closing": "If you feel like the star, soften until the lyric leads again.",
                },
                "guitar": {
                    "opening": "Brush the strings; the song lives in the gap between strokes.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Small room strum",
                            "body": (
                                "Down-up in 6/8, barely touching the strings. The first chorus hasn't "
                                "earned a big sound yet."
                            ),
                        },
                        {
                            "role": ROLE_CHORUS,
                            "heading": "Downbeats only",
                            "body": (
                                "Fuller strum on downbeats; let beats 4–6 breathe so the vocal can climb."
                            ),
                        },
                    ],
                    "closing": "Dynamics are the drama—not more chords.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: "6/8 sways; don't straighten it into march time.",
            ROLE_CHORUS: "The lift is emotional, not mechanical—widen, don't rush.",
        },
    },
    "hotelcalifornia": {
        "title": "Hotel California",
        "interpretation": {
            "emotional_character": (
                "Desert hypnosis—mysterious, seductive, and unhurried. The groove is a spell."
            ),
            "listen_for": "Each of the eight chords arriving like a landmark; the bass line descending with gravity.",
            "build_where": "Solo section and final choruses may burn hotter; verses stay trance-like.",
            "relax_where": "Long verse cycles—medium-soft, unchanging pulse.",
            "accompaniment": "Hypnotic foundation; when you add color, it should feel like mirages.",
            "rush_prone": "Collapsing four-bar holds into two because boredom feels scary.",
            "key_transitions": "Entering the solo cycle; final tag resolutions.",
            "master_challenge": "Making repetition feel intentional, not lazy.",
        },
        "practice_focus": {
            "Intermediate": {"general": "Desert trance · four-bar breath · solo as release valve"},
        },
        "lessons": {
            "Intermediate": {
                "guitar": {
                    "opening": (
                        "Hotel California rewards patience like almost no other pop song. The arpeggio "
                        "is the vocal—hum it until your thumb is bored."
                    ),
                    "journey": [
                        {
                            "role": ROLE_INTRO,
                            "heading": "Enter the desert",
                            "body": (
                                "Establish the thumb pattern and do not vary it for sport. "
                                "You're inviting the listener into a trance."
                            ),
                        },
                        {
                            "role": ROLE_VERSE,
                            "heading": "Eight landmarks",
                            "body": (
                                "Each chord gets its full weight—especially the four-bar sustains. "
                                "Count them aloud once so your body believes they're real."
                            ),
                        },
                        {
                            "role": ROLE_INSTRUMENTAL,
                            "heading": "The mirage breaks open",
                            "body": (
                                "The solo section is release, not chaos. Sing your phrases, return to "
                                "the cycle, remember the listener is still on the same road."
                            ),
                        },
                        {
                            "role": ROLE_OUTRO,
                            "heading": "Never quite leaving",
                            "body": (
                                "Fade inside the pattern; the hotel keeps running whether you stop or not."
                            ),
                        },
                    ],
                    "closing": "If you're bored, the audience is entranced. Trust the repeat.",
                },
                "piano": {
                    "opening": "Sparse comping paints heat—two notes per bar can be enough.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Heat haze",
                            "body": (
                                "Roll left-hand roots on 1 and 4; color on 2. Never fill the desert sky."
                            ),
                        },
                    ],
                    "closing": "Less notes, more gravity.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: "The descent is the story—each root is a footstep deeper in.",
            ROLE_INSTRUMENTAL: "Release within the same map; don't change the geography.",
        },
    },
    "allofme": {
        "title": "All of Me",
        "interpretation": {
            "emotional_character": (
                "Elegant surrender—romantic, jazz-tinged, confident without shouting."
            ),
            "listen_for": "Turnaround weight at the end of each A section; the song pivots on those bars.",
            "build_where": "Bridge and final chorus tags—polish and lift.",
            "relax_where": "Opening A sections—medium-soft swing, not showboating.",
            "accompaniment": "Suited and balanced—full enough to dance, never cluttered.",
            "rush_prone": "The turnaround—players skim it to get back to the top.",
            "key_transitions": "Turnarounds and bridge modulations.",
            "master_challenge": "Making standard motion feel inevitable and graceful.",
        },
        "practice_focus": {
            "Intermediate": {"general": "Turnaround gravity · swing at pop tempo · bridge polish"},
        },
        "lessons": {
            "Intermediate": {
                "piano": {
                    "opening": (
                        "All of Me is a carousel—every turn should feel level and inevitable. "
                        "Rush the turnaround and the romance trips."
                    ),
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "The A section story",
                            "body": (
                                "Shell voicings in the left; add the third in the right on beats 2 and 4. "
                                "Swing the eighths even at pop tempo—the song winks at jazz."
                            ),
                        },
                        {
                            "role": ROLE_BRIDGE,
                            "heading": "A new color",
                            "body": (
                                "The bridge should feel like stepping onto a balcony—brighter air, "
                                "same elegant posture."
                            ),
                        },
                    ],
                    "closing": "Practice the turnaround alone until it feels like a bow, not a bump.",
                },
                "guitar": {
                    "opening": "Three-note grips tell the whole story—barre washes are for another song.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Follow the bass letter",
                            "body": (
                                "Let slash-chord bass notes lead your fretting hand. "
                                "The melody lives in the top voice you imply, not in fills."
                            ),
                        },
                    ],
                    "closing": "Clean turns beat flashy strums.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: "The turnaround is the punctuation—give it a full stop.",
            ROLE_BRIDGE: "Contrast with charm, not volume.",
        },
    },
    "say": {
        "title": "Say",
        "interpretation": {
            "emotional_character": (
                "Late-night R&B honesty—the groove is cool, the vocal runs are hot."
            ),
            "listen_for": "Syncopated hits behind melisma—when the voice runs, the band thins.",
            "build_where": "Chorus stabs and ad-lib moments after the vocal rests.",
            "relax_where": "Verses—pocket deep in the back of the beat.",
            "accompaniment": "Rhythmic partner that steps aside for runs.",
            "rush_prone": "Playing through vocal melisma because silence feels awkward.",
            "key_transitions": "Verse pocket to chorus lift.",
            "master_challenge": "Supporting a virtuosic vocal without competing.",
        },
        "practice_focus": {
            "Intermediate": {"general": "Back-of-beat pocket · mute for melisma · chorus stabs only"},
        },
        "lessons": {
            "Intermediate": {
                "piano": {
                    "opening": "You're the drummer's roommate—if you clutter, the runs can't breathe.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Behind the beat",
                            "body": (
                                "Hit chords on the 'and' of 2 and 4. When the vocal runs, drop to one hand "
                                "or rest—silence is arrangement."
                            ),
                        },
                        {
                            "role": ROLE_CHORUS,
                            "heading": "Stabs, not washes",
                            "body": (
                                "Short, confident hits that mark the hook. Leave space for ad-libs after."
                            ),
                        },
                    ],
                    "closing": "If you're playing while the singer runs, you're wrong—even if the notes are right.",
                },
                "guitar": {
                    "opening": "Dry and staccato in the verse; open chords are a chorus reward.",
                    "journey": [
                        {
                            "role": ROLE_VERSE,
                            "heading": "Muted pocket",
                            "body": (
                                "Sixteenth-note chops, minimal sustain. You're percussion with pitch."
                            ),
                        },
                    ],
                    "closing": "Groove first, harmony second, ego never.",
                },
            },
        },
        "harmony_tips": {
            ROLE_VERSE: "The pocket sits behind the click—luxurious, not lazy.",
            ROLE_CHORUS: "Hits mark the hook; everything else is clearance for the voice.",
        },
    },
}
