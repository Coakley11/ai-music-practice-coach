"""Real-app level defaults, read-only toggles and native notation acceptance."""
import copy,re,json

def run(page,request,select,out):
    select(page,'Instrument','Flute');select(page,'Level','Beginner')
    def card():return page.locator('[class*="st-key-music_coach_insight_panel_"]').last
    def toggle():return card().get_by_role('checkbox',name='Show note names',exact=True)
    def shot(name):
        label=toggle().locator('xpath=ancestor::label[1]')
        metric=label.evaluate('(e)=>({text:e.innerText,scroll:e.scrollWidth,width:e.clientWidth})')
        assert 'Show note names' in metric['text'] and metric['scroll']<=metric['width']+1
        toggle().evaluate('(e)=>e.scrollIntoView({block:"center"})');page.wait_for_timeout(250)
        page.screenshot(path=str(out/name))
    def ask(q,cue,tag):return request(page,q,cue,'note-display-'+tag)[0]
    initial=ask('Give me a 4-bar C major scale pattern.','Try this','beginner-scale')
    assert initial['response']['diagnostics']['note_name_rows'] and toggle().is_checked()
    original_abc=initial['response']['notation_abc']
    def visible_rows():
        return card().locator('[data-testid="stExpander"]').filter(has_text='Written note names').locator('details[open]').count()>0
    assert visible_rows()
    for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(500)
        toggle().scroll_into_view_if_needed();shot(label+'-beginner-note-names.png')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    select(page,'Level','Intermediate');page.wait_for_timeout(600)
    assert not toggle().is_checked() and not visible_rows()
    shown=ask('Show me the note names.','Written note names','explicit-show')
    assert shown['response']['notation_abc']==original_abc and shown['plan']==initial['plan'] and shown['history']==initial['history']
    assert toggle().is_checked() and visible_rows()
    select(page,'Level','Advanced');page.wait_for_timeout(600);assert toggle().is_checked()
    hidden=ask('Hide the note names.','Note names are hidden','explicit-hide')
    assert hidden['response']['notation_abc']==original_abc and hidden['plan']==initial['plan'] and hidden['history']==initial['history']
    assert not toggle().is_checked() and not visible_rows()
    measure=ask('What are the notes in measure 4?','Written note names','measure-four')
    assert all(x['bar']==4 for x in measure['response']['diagnostics']['note_name_rows'])
    assert measure['response']['notation_abc']==original_abc
    explain=ask('Explain the notes in this exercise.','Written note names','explain-readonly')
    assert explain['response']['notation_abc']==original_abc and explain['history']==initial['history']
    ask('Hide the note names.','Note names are hidden','hide-again')
    select(page,'Instrument','Saxophone');select(page,'Level','Advanced')
    lick=ask('Give me an advanced jazz lick in G major.','Try this','advanced-jazz-lick')
    assert lick['response']['diagnostics']['note_name_rows'] and not toggle().is_checked() and not visible_rows()
    for label,width,height in [('desktop',1440,1000),('mobile',390,844)]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(500)
        shot(label+'-advanced-jazz-lick-clean.png')
    jazz=ask('Give me an advanced alto sax finger-buster with accents.','finger coordination','advanced-sax')
    assert not toggle().is_checked() and not visible_rows()
    rows=jazz['response']['diagnostics']['note_name_rows'];assert rows
    # Real revision and exact history restore, including displayed written pitches.
    slower=ask('Make it slower.','Updated only','slower')
    undo=ask('Undo.','Undo','undo');redo=ask('Redo.','Redo','redo')
    assert undo['plan']==jazz['plan'] and redo['plan']==slower['plan']
    assert undo['response']['diagnostics']['note_name_rows']==rows
    for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(500)
        shot(label+'-advanced-clean-staff.png')
        assert not visible_rows() and page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    # A real chart and full-form output rather than invented section names.
    import walk_guitar_shape_key as catalog_ui,walk_creative_backing_matrix as existing_ui
    catalog_ui.OUT=out/'catalog';existing_ui.OUT=out/'catalog';catalog_ui.OUT.mkdir(exist_ok=True)
    page.set_viewport_size({'width':1440,'height':1000});page.wait_for_timeout(600)
    assert catalog_ui.pick_song(page,[],'Blue Bossa','Jazz')
    page.locator('.st-key-studio_quick_nav_btn_practice button:visible').first.click()
    page.get_by_test_id('stMainBlockContainer').get_by_role('textbox',name='Question',exact=True).wait_for(timeout=90000)
    select(page,'Level','Intermediate')
    song=ask('Give me a guide-tone exercise over the whole song.','guide','song-aware')
    assert not toggle().is_checked() and not visible_rows() and song['response']['diagnostics']['note_name_rows']
    for label,width,height in [('desktop',1440,1000),('mobile',390,844)]:
        page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(500)
        shot(label+'-song-clean-staff.png')
    (out/'note-display-acceptance.json').write_text(json.dumps({'beginner_rows':initial['response']['diagnostics']['note_name_rows'],'advanced_rows':rows,'song_rows':song['response']['diagnostics']['note_name_rows'],'stored_abc_preserved_for_display_requests':True,'history_preserved_for_display_requests':True,'exact_undo_redo':True},indent=2),encoding='utf-8')
