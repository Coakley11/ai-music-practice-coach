"""Current capabilities: navigation to existing pages, never entitlement bypasses."""
CAPABILITIES = (
    ('log', 'Practice Log insights', 'AI-assisted analysis of saved practice evidence, when configured.'),
    ('analysis', 'Upload Analysis', 'Recording analysis and optional AI feedback; available analysis modes depend on setup and access.'),
    ('creative', 'Creative Lab', 'Harmony and improvisation tools; optional AI guidance where enabled.'),
    ('creative', 'Song-Aware Coaching', 'Source-aware guided practice plans in Creative Lab; these are not all OpenAI-generated.'),
    ('creative', 'Missions and guided practice', 'Existing guided exercises in Creative Lab; access checks remain on the destination page.'),
    ('composer', 'Composition Studio', 'Write and save compositions with the shared music tools; optional coaching is separate.'),
    ('backing', 'Backing Tracks and Key Cycling', 'Music playback and practice tools, not an OpenAI requirement.'),
    ('practice', 'Practice and melody coaching', 'Song charts, melody tools and practice guidance; optional AI tools depend on configuration.'),
)
FUTURE_DIRECTIONS = (
    'Dedicated chord recognition from recordings.',
    'Onset-level alignment models for more precise timing feedback.',
)


def render_coaching_hub(st, session, navigate, rerun):
    st.markdown('#### Available now')
    st.caption('Tools live on their existing studio pages. OpenAI-specific actions require configuration; feature flags and membership checks still apply there.')
    for index, (page, title, description) in enumerate(CAPABILITIES):
        if st.button(title, key=f'openai_hub_current_{index}', use_container_width=True):
            navigate(session, page)
            rerun()
        st.caption(description)
    st.markdown('#### Future directions')
    st.caption('Roadmap ideas, not currently available tools or release promises. Existing recording comparisons and practice summaries are already available elsewhere in the app.')
    for idea in FUTURE_DIRECTIONS:
        st.markdown('- ' + idea)
