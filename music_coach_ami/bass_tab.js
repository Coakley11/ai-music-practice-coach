/* Pinned ABCJS 6.4.4 geometry companion. No pitches/fingerings are chosen here. */
function amiRenderBassTab(id, abc, tab) {
  const box=document.getElementById(id), NS='http://www.w3.org/2000/svg';
  const width=Math.max(420,Math.min(720,window.innerWidth-40));
  const perLine=window.innerWidth<560?1:2;
  const breaks=[];for(let n=perLine;n<tab.bars;n+=perLine)breaks.push(n);
  const tunes=ABCJS.renderAbc(id,abc,{responsive:'resize',staffwidth:width,paddingbottom:145,wrap:{minSpacing:1.8,maxSpacing:2.7,preferredMeasuresPerLine:perLine},oneSvgPerLine:true,add_classes:true});
  try {
    if(tab.version!==1||tab.abc!==abc.trim()||tab.offset!==12||tab.strings.join('')!=='GDAE')throw Error('stored TAB does not match this score');
    let index=0,system=0;
    const drawn=[],systems=[];
    const add=(parent,tag,attrs,text)=>{let e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;parent.appendChild(e);return e};
    for(const tune of tunes) for(const line of tune.lines||[]) {
      if(!line.staff)continue;
      if(line.staff.length!==1||line.staff[0].voices.length!==1)throw Error('only one bass voice is supported');
      const voice=line.staff[0].voices[0], notes=voice.filter(e=>e.el_type==='note'), bars=voice.filter(e=>e.el_type==='bar');
      if(!notes.length)continue;
      const abs=notes[0].abselem;
      const elements=abs.elemset||[];
      const svg=elements.map(e=>e.ownerSVGElement||e).find(e=>e&&e.tagName&&e.tagName.toLowerCase()==='svg')||box.querySelectorAll('svg')[system];
      if(!svg)throw Error('score geometry unavailable');
      const group=tune.engraver.staffgroups[system], staff=group.staffs[0];
      const top=staff.absoluteY+36;
      const xs=notes.concat(bars).map(e=>e.abselem.x);const left=Math.min(...xs)-14,right=Math.max(...xs)+8;
      const g=add(svg,'g',{'class':'ami-bass-tab','role':'group','aria-label':'Four-string bass TAB, G D A E top to bottom','data-system':system,stroke:'none'});
      for(let string=1;string<=4;string++){
        const y=top+(string-1)*14;
        add(g,'line',{x1:left,y1:y,x2:right,y2:y,stroke:'#64748b','stroke-width':.8,'class':'ami-bass-tab-string','data-string':string,'data-name':tab.strings[string-1]});
        add(g,'text',{x:left-18,y:y+4,'font-size':13,'font-family':'Arial','font-weight':'bold'},tab.strings[string-1]);
      }
      for(const bar of bars)add(g,'line',{x1:bar.abselem.x,y1:top,x2:bar.abselem.x,y2:top+42,stroke:'#334155','class':'ami-bass-tab-bar','data-score-x':bar.abselem.x});
      for(const e of notes){
        const t=tab.events[index++];if(!t)throw Error('extra staff event');
        if(Math.abs(e.duration-t.beats[0]/t.beats[1]/4)>1e-9||!!e.rest!==t.rest)throw Error('staff and TAB timing disagree');
        if(!t.rest&&(e.pitches.length!==1||e.pitches[0].pitch!==t.diatonic||e.pitches[0].startTie||e.pitches[0].endTie))throw Error('unsupported pitch or tie');
        const x=e.abselem.x+3;
        const attributes={'class':t.rest?'ami-bass-tab-rest':'ami-bass-tab-fret','data-event':t.id,'data-bar':t.bar,'data-beat':t.beat,
          'data-duration':t.duration,'data-onset':t.onset.join('/'),'data-beats':t.beats.join('/'),'data-score-x':e.abselem.x,
          'data-string':t.string,'data-fret':t.fret,'data-written':t.written_midi,'data-sounding':t.sounding_midi};
        const noteGroup=add(g,'g',attributes);
        const y=t.rest?top+21:top+(t.string-1)*14;
        add(noteGroup,'rect',{x:x-(t.rest?16:10),y:y-9,width:t.rest?32:20,height:16,fill:'white'});
        add(noteGroup,'text',{x,y:y+4,'text-anchor':'middle','font-family':'Arial','font-size':t.rest?10:14,'font-weight':'bold'},t.rest?'rest':t.fret);
        const value={whole:'1',half:'½',quarter:'¼',eighth:'⅛',sixteenth:'1/16'}[t.duration];
        if(!value)throw Error('unsupported note value');
        add(noteGroup,'text',{x,y:top+66,'text-anchor':'middle','font-family':'Arial','font-size':10,'class':'ami-bass-tab-duration'},value);
        add(noteGroup,'title',{},`${t.rest?'Rest':tab.strings[t.string-1]+' string, fret '+t.fret}; bar ${t.bar+1}, beat ${t.beat}; ${t.duration}${t.articulation?', '+t.articulation:''}`);
        drawn.push({event:t.id,system,x,staffX:e.abselem.x,string:t.string,fret:t.fret,rest:t.rest});
      }
      const vb=svg.viewBox.baseVal;const bottom=top+86;
      if(bottom>vb.height){svg.setAttribute('viewBox',`${vb.x} ${vb.y} ${vb.width} ${bottom}`);if(svg.parentElement.style.paddingBottom)svg.parentElement.style.paddingBottom=(bottom/vb.width*100)+'%'}
      systems.push({native:voice.filter(e=>e.abselem).flatMap(e=>e.abselem.elemset||[]),tab:g});
      system++;
    }
    if(index!==tab.events.length)throw Error('missing staff event');
    // ABCJS retains cumulative system coordinates in its per-line SVGs.
    // Crop each viewport to its own real content, including the companion TAB.
    const title=document.createElement('h3');title.textContent=(abc.split('\n').find(l=>l.startsWith('T:'))||'T:Bass exercise').slice(2);
    title.style.cssText='font:600 18px/1.4 Arial;overflow-wrap:anywhere;margin:10px 0;max-width:'+Math.min(720,window.innerWidth-24)+'px';box.prepend(title);
    box.querySelectorAll('.abcjs-title,[data-name="title"]').forEach(e=>e.remove());
    for(const svg of box.querySelectorAll('svg')){
      const b=svg.getBBox(),v=svg.viewBox.baseVal;
      if(!b.height){const holder=svg.parentElement;if(holder!==box&&holder.childElementCount===1)holder.remove();else svg.remove();continue}
      const w=Math.max(v.width,b.x+b.width+12),h=b.height+24;
      svg.setAttribute('viewBox',`0 ${b.y-12} ${w} ${h}`);
      if(svg.parentElement.style.paddingBottom)svg.parentElement.style.paddingBottom=(h/w*100)+'%';
    }
    const layouts=systems.map(s=>{const rects=s.native.map(e=>e.getBoundingClientRect()).filter(r=>r.height),t=s.tab.getBoundingClientRect();return {nativeTop:Math.min(...rects.map(r=>r.top)),nativeBottom:Math.max(...rects.map(r=>r.bottom)),tabTop:t.top,tabBottom:t.bottom}});
    for(let i=0;i<layouts.length;i++){
      if(layouts[i].tabTop<layouts[i].nativeBottom+4)throw Error('staff/TAB collision');
      if(i&&layouts[i].nativeTop<layouts[i-1].tabBottom+4)throw Error('adjacent system collision');
    }
    (window.__amiBassTabs||(window.__amiBassTabs=[])).push({id,ok:true,events:drawn,systems:system,layouts});
  } catch(error) {
    box.querySelectorAll('.ami-bass-tab').forEach(e=>e.remove());
    const p=document.createElement('p');p.className='ami-bass-tab-warning';p.textContent='TAB unavailable: '+error.message+'. The standard staff remains available.';box.appendChild(p);
    (window.__amiBassTabs||(window.__amiBassTabs=[])).push({id,ok:false,error:error.message});
  }
  return tunes;
}
