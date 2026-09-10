"""Retained Python source for the notification style lookbook and its previews.

Run with the repo's preferred Python 3.11. Requires Pillow, reportlab, PyMuPDF.
This renders design concepts only; it does not modify or restart the notifier.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import re

from PIL import Image, ImageDraw, ImageFont
import fitz
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

OUT = Path(__file__).resolve().parent
PDF = OUT.parent / 'pdf' / 'codex-notify-style-lookbook.pdf'
PREVIEWS = OUT / 'previews'
PAGES = OUT / 'pages'
SCALE = 3
FONTDIR = Path('C:/Windows/Fonts')
FONTS = {'regular': 'segoeui.ttf', 'bold': 'segoeuib.ttf',
         'light': 'segoeuil.ttf', 'mono': 'consola.ttf'}
PW, PH = 841.89, 595.28
INK, MUTED, PAPER, LINE = '#18252D', '#53636D', '#F6F8F9', '#DCE3E7'
PROJECT = 'windows-notify-codex'
LONG = ('The notification update is ready to review. Spacing, typography, and status '
        'colors are consistent. Files & folders keep their names. A longer message '
        'should remain readable and end cleanly when there is more text than the card can show.')


@dataclass
class Style:
    id: int
    name: str
    family: int
    layout: str
    bg: str
    fg: str
    body: str
    border: str
    accent: str
    radius: int = 10
    width: int = 460
    height: int = 156
    inset: str = ''
    why: str = ''
    tradeoff: str = ''


FAMILIES = [
    ('Quiet dark', 'Familiar dark cards with different levels of structure and emphasis.'),
    ('Clean light', 'Bright, restrained surfaces for light desktops and softer contrast.'),
    ('Compact', 'Smaller footprints, with deliberate tradeoffs in message capacity.'),
    ('Typography first', 'Let text order and type choices do most of the visual work.'),
    ('Muted color', 'A little personality through low-saturation surfaces and accents.'),
    ('Subtle structure', 'Minimal changes to edges, grouping, and status placement.'),
]


def s(i, name, family, layout, colors, why, tradeoff, **kw):
    return Style(i, name, family, layout, *colors.split(), why=why, tradeoff=tradeoff, **kw)


STYLES = [
    s(1, 'Refined baseline', 0, 'dot', '#1E1F22 #F4F5F7 #C7CAD1 #414349 #85C7AA',
      'The closest direction to the current app: familiar proportions and a small status dot.',
      'The project stays in the body, so a long workspace name competes with the message.'),
    s(2, 'Graphite quiet', 0, 'plain', '#232629 #F1F3F4 #BFC5C9 #34393D #AEC8BD',
      'A calm, text-only card. No icon, badge, or extra metadata is needed to read it.',
      'Completion and attention rely on the wording rather than an additional visual marker.', radius=8),
    s(3, 'Ink frame', 0, 'rule', '#15191D #EDF1F4 #B9C2CB #53606B #A8C0D5',
      'A precise outline and divider make the card easy to distinguish from a dark editor.',
      'The stronger frame is more visible than the other dark options.', radius=4),
    s(4, 'Slate metadata', 0, 'meta', '#252D36 #F1F4F7 #C1CAD3 #404B57 #9DBBDC',
      'A small project line gives the title and the message their own space.',
      'An extra text row makes this one slightly taller.', height=172),
    s(5, 'Charcoal ring', 0, 'ring', '#242426 #F4F3F3 #C7C5C8 #414044 #B3CDBB',
      'An outlined status symbol is easy to spot without a filled icon tile.',
      'The icon column leaves less horizontal room for the message.', radius=14),
    s(6, 'Obsidian hairline', 0, 'toprule', '#17191B #F3F4F5 #BEC4C8 #303539 #94C4B1',
      'A thin top accent gives a nearly black card a restrained identity.',
      'The edge treatment is more decorative than a simple dot.', radius=7),
    s(7, 'Porcelain', 1, 'dot', '#FEFEFD #202B32 #53616A #D9E0E3 #3F7F64',
      'A crisp light counterpart to the refined baseline, with the same reading order.',
      'A white card attracts more attention over a very dark desktop.'),
    s(8, 'Paper rule', 1, 'rule', '#FFFFFF #293138 #56616A #D7DEE3 #426B84',
      'Straightforward typography and a fine separator give it an editorial feel.',
      'The divider creates a more formal, document-like appearance.', radius=3),
    s(9, 'Warm stone', 1, 'ring', '#F5F2EC #35342F #625F57 #DCD7CE #59745F',
      'A warm neutral surface avoids the glare of pure white.',
      'The cream tone may feel less at home beside a cool gray interface.', radius=12),
    s(10, 'Chalk', 1, 'plain', '#F4F6F7 #29353D #596A73 #F4F6F7 #466E64',
      'The lightest visual treatment: soft surface, text, and breathing room.',
      'Without a visible border it can blend into similarly light backgrounds.', radius=14),
    s(11, 'Pearl badge', 1, 'badge', '#FCFDFE #293642 #536471 #DCE3E9 #427361',
      'A small status badge separates state from project and message.',
      'The badge and project row add structure beyond the current two-part card.', radius=12, height=166),
    s(12, 'Ivory project', 1, 'project', '#FBF8F1 #36342D #686359 #E2DDD2 #677650',
      'The project name becomes the main heading for people juggling several workspaces.',
      'The completion wording is smaller than the project heading.', radius=8, height=166),
    s(13, 'Slim rail', 2, 'rail', '#22272C #F2F4F5 #C1C9CE #3B444B #91BCAE',
      'A narrow accent rail and reduced height preserve a clear two-part hierarchy.',
      'Only a short message fits before truncation.', height=112, radius=8),
    s(14, 'Compact pill', 2, 'pill', '#F9FAFB #27353F #5D6B76 #D7E0E6 #46775D',
      'A small rounded capsule works well for short, glanceable updates.',
      'The body is a single line; long messages are intentionally abbreviated.', height=92, radius=42),
    s(15, 'Tight stack', 2, 'meta', '#25282D #F1F3F5 #C0C6D0 #414750 #ABB9D0',
      'Keeps project, state, and message separate in a compact vertical stack.',
      'The extra project row leaves room for only one body line.', height=120, radius=6),
    s(16, 'Inline check', 2, 'ring', '#EDF2F3 #23353B #51656C #CFDADD #44766A',
      'A small status symbol anchors a low-height card with strong horizontal alignment.',
      'The symbol column and short height both reduce message space.', height=108, radius=10),
    s(17, 'Mini panel', 2, 'dot', '#20252A #F2F5F6 #BDC8CE #3D484F #9BBDB2',
      'A narrower card saves horizontal space while retaining the familiar hierarchy.',
      'Workspace names and messages wrap sooner.', width=360, height=136, radius=9),
    s(18, 'Wide strip', 2, 'plain', '#F8F8F7 #2B3238 #5D666F #DADDDF #487764',
      'A wide, shallow strip favors quick scanning of short updates.',
      'It takes more horizontal space and offers only one body line.', width=540, height=96, radius=5),
    s(19, 'Editorial dark', 3, 'editorial', '#202224 #F3F4F4 #C1C6C9 #3B4043 #A7C5B8',
      'A larger project heading makes workspace recognition the first thing you notice.',
      'Long project names need ellipsis even when the message itself is short.', height=176, radius=10),
    s(20, 'Editorial light', 3, 'editorial', '#FCFCFA #28332F #5A6761 #DCE1DA #55715C',
      'A quiet, light version of the project-led hierarchy with generous spacing.',
      'The large project heading feels more like a small card than a conventional toast.', height=176, radius=8),
    s(21, 'Mono note', 3, 'mono', '#1D2328 #EDF3F5 #BCCBD1 #3B4A53 #9BBCC8',
      'A monospace status line and project name give it a precise developer-tool character.',
      'Monospace metadata uses more width and feels more technical.', height=166, radius=5),
    s(22, 'Quiet hierarchy', 3, 'project', '#F4F5F7 #303744 #626B7B #DADFE7 #67778B',
      'A small status line above a project heading creates a clear, restrained reading order.',
      'The status has less visual emphasis than in the baseline.', height=166, radius=10),
    s(23, 'Footer status', 3, 'footer', '#26282B #F1F3F4 #C3C7CD #464B51 #A8C1B5',
      'The message leads; a quiet footer carries the status after you have read the result.',
      'The completion or attention state is less immediately prominent.', height=156, radius=7),
    s(24, 'Accent typography', 3, 'accenttype', '#F9FAFA #28383D #5C6B70 #DAE2E3 #3E7266',
      'The title itself carries the accent, leaving the rest of the card completely plain.',
      'The color treatment is subtler than a status icon, especially at a glance.', radius=8),
    s(25, 'Sage wash', 4, 'dot', '#EDF3EE #2D3E33 #53685A #CCDCCE #4D7D5E',
      'A faint sage surface gives the card warmth while keeping the layout familiar.',
      'A colored surface is more of a personal preference than a neutral system look.', radius=12),
    s(26, 'Blue mist', 4, 'toprule', '#222D38 #EEF4F9 #B9CBD8 #415364 #9BBCD6',
      'A cool dark surface and fine top line pair naturally with a blue-gray desktop.',
      'The blue accent is an identity color; status is still communicated by the title.', radius=10),
    s(27, 'Sand', 4, 'plain', '#F4EFE6 #3D362B #6D6251 #DED3C3 #796D4E',
      'Warm neutrals and a text-only layout keep the color treatment understated.',
      'The warmth may clash with a strongly cool or blue desktop.', radius=8),
    s(28, 'Dusty lilac', 4, 'badge', '#F1EEF6 #3B344B #6B607C #DBD3E7 #78658C',
      'A desaturated violet surface and small badge add personality without bright colors.',
      'The badge is a stronger styling choice than the baseline dot.', height=166, radius=12),
    s(29, 'Mineral teal', 4, 'ring', '#1E2D30 #EDF5F4 #B5CCC9 #395257 #95C3BB',
      'A deep teal surface and outlined status symbol feel calm but distinctive.',
      'The icon column makes long messages wrap sooner.', radius=12),
    s(30, 'Soft silver', 4, 'rule', '#30343A #F3F5F7 #CAD1D9 #555D67 #BAC6D2',
      'A slightly lighter dark surface reduces the contrast jump against medium-gray apps.',
      'It has less separation from medium-gray backgrounds than a near-black card.', radius=6),
    s(31, 'Left rule', 5, 'rail', '#1E252B #F0F4F6 #BFCBD2 #3E4B55 #9FC4B4',
      'One thin vertical accent gives a strong visual anchor with very little decoration.',
      'The left accent is more noticeable than a small status dot.', radius=10),
    s(32, 'Header band', 5, 'band', '#F9FAFB #2B3941 #596B75 #D7E0E5 #547966',
      'A softly tinted header separates status from the message without a hard divider.',
      'Two surface tones give it a more structured appearance.', inset='#EAF0ED', radius=10),
    s(33, 'Split surface', 5, 'split', '#242A30 #F1F5F7 #BFCCD5 #42505B #A3C5B9',
      'A small state column keeps the message area visually organized.',
      'The state column takes space from the project and message.', inset='#2D373C', height=164, radius=10),
    s(34, 'Inset message', 5, 'inset', '#F7F9FA #2A3840 #586A75 #D6E0E6 #557E69',
      'A pale inset groups the message while the status stays in the outer header.',
      'The extra surface makes it a little less spare than the text-only options.', inset='#EDF1F4', height=168, radius=12),
    s(35, 'Floating check', 5, 'floating', '#25282D #F3F5F7 #C5CDD6 #424B57 #A8C7B7',
      'A single softly filled status circle creates a polished focal point.',
      'The larger symbol makes this the most icon-led option.', radius=16),
    s(36, 'Corner mark', 5, 'corner', '#FCFBF8 #323831 #616B60 #E0E3DA #6A8265',
      'Two short corner strokes give the card a recognizable signature without a full accent rail.',
      'The corner treatment is decorative rather than functional.', radius=5),
]


def font(size, kind='regular'):
    return ImageFont.truetype(str(FONTDIR / FONTS[kind]), round(size * SCALE))


def mix(a, b, t):
    aa, bb = tuple(bytes.fromhex(a[1:])), tuple(bytes.fromhex(b[1:]))
    return '#' + ''.join(f'{round(x * (1-t) + y*t):02x}' for x, y in zip(aa, bb))


def is_dark(color):
    return sum(bytes.fromhex(color[1:])) < 390


def wrap(draw, text, f, width, maxlines):
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=f) <= width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
                while draw.textlength(line, font=f) > width:
                    cut = len(line)
                    while cut > 1 and draw.textlength(line[:cut], font=f) > width:
                        cut -= 1
                    lines.append(line[:cut])
                    line = line[cut:]
        if line:
            lines.append(line)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
        while lines[-1] and draw.textlength(lines[-1] + '...', font=f) > width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + '...'
    return lines


def render_card(st, state='completion', long=False):
    w, h = st.width, st.height
    im = Image.new('RGBA', (w*SCALE, h*SCALE), st.bg)
    d = ImageDraw.Draw(im)
    accent = ('#DDB879' if is_dark(st.bg) else '#956A23') if state == 'attention' else st.accent
    title = 'Codex needs attention' if state == 'attention' else 'Codex task finished'
    short = 'Choose an option to continue. Your input is needed.' if state == 'attention' else 'The update is ready to review. All checks passed.'
    message = LONG if long else short
    def rect(box, fill, radius=0, outline=None):
        b = tuple(round(v*SCALE) for v in box)
        if radius:
            d.rounded_rectangle(b, round(radius*SCALE), fill=fill, outline=outline, width=SCALE)
        else:
            d.rectangle(b, fill=fill, outline=outline, width=SCALE)
    def line(points, fill, width=1):
        d.line([(round(x*SCALE), round(y*SCALE)) for x,y in points], fill=fill, width=round(width*SCALE))
    def text(x, y, value, size=14, color=None, kind='regular', width=None, rows=1, leading=None):
        ff = font(size, kind)
        width = (w-x-20) if width is None else width
        strings = wrap(d, value, ff, width*SCALE, rows)
        leading = leading or size*1.42
        for index, value in enumerate(strings):
            assert x+width <= w+0.1 and y+index*leading+size <= h+0.1, (st.name, value)
            d.text((round(x*SCALE), round((y+index*leading)*SCALE)), value, font=ff,
                   fill=color or st.body, anchor='lt')
        return len(strings)
    def body(x, y, include_project=True, size=14, bottom=18, width=None):
        value = (PROJECT + ': ' if include_project else '') + message
        leading = size*1.42
        rows = max(1, math.floor((h-bottom-y-size)/leading)+1)
        return text(x,y,value,size,width=width,rows=rows,leading=leading)
    def dot(x,y):
        d.ellipse((int((x-3)*SCALE),int((y-3)*SCALE),int((x+3)*SCALE),int((y+3)*SCALE)),fill=accent)
    def symbol(x,y,r=12,filled=False):
        d.ellipse((int((x-r)*SCALE),int((y-r)*SCALE),int((x+r)*SCALE),int((y+r)*SCALE)),
                  fill=mix(st.bg,accent,.13) if filled else None, outline=accent,width=SCALE)
        if state=='attention':
            line([(x,y-5),(x,y+1)],accent,1.6)
            d.ellipse((int((x-.8)*SCALE),int((y+4)*SCALE),int((x+.8)*SCALE),int((y+5.6)*SCALE)),fill=accent)
        else:
            line([(x-5,y),(x-1,y+4),(x+6,y-4)],accent,1.7)
    rect((.5,.5,w-1,h-1),st.bg,st.radius,st.border)
    layout=st.layout
    if layout in ('dot','plain','accenttype','toprule','rail','corner'):
        x=34 if layout=='dot' else 22 if layout=='rail' else 20
        if layout=='dot': dot(23,27)
        if layout=='toprule': rect((16,1,w-16,3),accent,1)
        if layout=='rail': rect((1,15,4,h-15),accent,1)
        if layout=='corner':
            line([(1,20),(1,1),(20,1)],accent,2)
        text(x,18,title,16,accent if layout=='accenttype' else st.fg,'bold')
        body(22 if layout=='rail' else 20,52,size=13 if h<120 else 14)
    elif layout=='rule':
        text(20,18,title,16,st.fg,'bold')
        line([(20,46),(w-20,46)],st.border)
        body(20,60)
    elif layout=='meta':
        text(20,15,'CODEX / '+PROJECT,10.5,st.body,width=w-40)
        text(20,39,title,16,st.fg,'bold')
        body(20,73,False,size=13)
    elif layout in ('ring','floating'):
        floating=layout=='floating'
        symbol(37 if floating else 31,31,16 if floating else 11,floating)
        x=66 if floating else 53
        text(x,19,title,15.5,st.fg,'bold')
        body(x,52,size=13 if h<120 else 14)
    elif layout=='pill':
        symbol(29,32,10)
        text(51,17,title,14.5,st.fg,'bold')
        text(51,43,PROJECT+': '+message,12.5,width=w-78)
    elif layout=='badge':
        text(20,17,'CODEX',10.5,st.body,'bold')
        badge='ATTENTION' if state=='attention' else 'COMPLETED'
        rect((w-111,12,w-18,34),mix(st.bg,accent,.12),10)
        text(w-103,17,badge,9.5,accent,'bold',width=83)
        text(20,49,PROJECT,16,st.fg,'bold')
        body(20,80,False)
    elif layout in ('project','editorial'):
        dot(23,22)
        text(34,16,title,11,st.body)
        text(20,42,PROJECT,21 if layout=='editorial' else 17,st.fg,
             'light' if layout=='editorial' else 'bold')
        body(20,83 if layout=='editorial' else 78,False)
    elif layout=='mono':
        text(20,17,'CODEX / '+('ATTENTION' if state=='attention' else 'DONE'),12.5,accent,'mono')
        line([(20,43),(w-20,43)],st.border)
        text(20,57,PROJECT,12,st.fg,'mono')
        body(20,84,False,size=13)
    elif layout=='footer':
        text(20,19,PROJECT,15,st.fg,'bold')
        text(20,49,message,14,rows=3)
        line([(20,h-40),(w-20,h-40)],st.border)
        dot(23,h-22)
        text(34,h-28,title,11.5,st.body)
    elif layout=='band':
        rect((1,1,w-2,44),mix(st.bg,accent,.10))
        dot(23,24)
        text(34,16,title,15,st.fg,'bold')
        body(20,61)
    elif layout=='split':
        rect((1,1,99,h-2),st.inset)
        text(19,20,'CODEX',10,st.body,'bold',width=69)
        symbol(49,66,13)
        text(11,94,'ATTENTION' if state=='attention' else 'FINISHED',9.5,accent,'bold',width=83)
        text(117,21,PROJECT,14,st.fg,'bold')
        body(117,54,False,size=13)
    elif layout=='inset':
        dot(23,25)
        text(34,17,title,15.5,st.fg,'bold')
        rect((13,48,w-14,h-13),st.inset,7)
        body(25,62,size=13.5,bottom=25,width=w-50)
    else:
        raise ValueError(layout)
    mask=Image.new('L',im.size,0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,w*SCALE-1,h*SCALE-1),radius=st.radius*SCALE,fill=255)
    im.putalpha(mask)
    return im


def save_previews():
    PREVIEWS.mkdir(parents=True,exist_ok=True)
    for st in STYLES:
        for state,long in [('completion',False),('attention',False),('long',True)]:
            render_card(st, 'completion' if long else state, long).save(PREVIEWS/f'{st.id:02d}-{state}.png')
    (OUT/'styles.json').write_text(json.dumps([vars(st) for st in STYLES],indent=2),encoding='utf-8')


class Book:
    def __init__(self):
        PDF.parent.mkdir(parents=True,exist_ok=True)
        for key,value in FONTS.items():
            pdfmetrics.registerFont(TTFont(key,str(FONTDIR/value)))
        self.c=canvas.Canvas(str(PDF),pagesize=(PW,PH),pageCompression=1)
        self.c.setTitle('Codex Notify - 36 Minimal Notification Styles')
        self.c.setAuthor('Codex')
        self.c.setSubject('A 48-page visual lookbook of Python-rendered notification design concepts')
        self.n=0
    def txt(self,x,y,t,size=12,color=INK,font='regular'):
        self.c.setFillColor(HexColor(color));self.c.setFont(font,size)
        self.c.drawString(x,PH-y-size*.82,t)
    def para(self,x,y,t,width,size=10.5,color=MUTED,font='regular',leading=None):
        leading=leading or size*1.5
        yy=y
        for paragraph in t.split('\n'):
            ln=''
            for word in paragraph.split():
                nxt=(ln+' '+word).strip()
                if pdfmetrics.stringWidth(nxt,font,size)>width and ln:
                    self.txt(x,yy,ln,size,color,font); yy+=leading; ln=word
                else: ln=nxt
            if ln:self.txt(x,yy,ln,size,color,font);yy+=leading
        return yy
    def box(self,x,y,w,h,fill,r=0,stroke=None):
        self.c.setFillColor(HexColor(fill))
        self.c.setStrokeColor(HexColor(stroke or fill))
        self.c.roundRect(x,PH-y-h,w,h,r,fill=1,stroke=bool(stroke))
    def rule(self,y):self.box(40,y,PW-80,.6,LINE)
    def page(self,section,dark=False,bookmark=None):
        self.n+=1
        self.box(0,0,PW,PH,'#172128' if dark else PAPER)
        color='#AFBEC6' if dark else MUTED
        self.txt(40,25,'CODEX NOTIFY  /  DESIGN LOOKBOOK',9,color,'bold')
        self.txt(550,25,section.upper(),8.5,color)
        self.txt(40,PH-27,'36 concepts  /  Python-rendered design studies',8,color)
        self.txt(PW-67,PH-27,f'{self.n:02d}',9,color,'bold')
        if bookmark:self.c.bookmarkPage(bookmark)
    def end(self):self.c.showPage()
    def preview(self,st,x,y,width=345,state='completion',panel=True):
        file=PREVIEWS/f'{st.id:02d}-{state}.png'
        height=width*st.height/st.width
        if panel:
            self.box(x-12,y-12,width+24,height+24,'#E8EDF0',10)
        self.c.drawImage(ImageReader(str(file)),x,PH-y-height,width,height,mask='auto')
        return height
    def cover(self):
        self.page('36 streamlined directions',True,'cover')
        self.c.addOutlineEntry('Start here','cover',0)
        self.txt(40,84,'Small notifications.',38,'#F4F7F8','bold')
        self.txt(40,134,'Many directions.',38,'#F4F7F8','light')
        self.para(42,203,'A visual study of 36 minimal looks for your Codex notifier.\nCompare the shapes, text hierarchy, surfaces, and status treatments.',640,14,'#B5C3CB')
        for st,x,y in [(STYLES[0],42,294),(STYLES[6],420,294),(STYLES[30],232,423)]:
            self.preview(st,x,y,345,panel=False)
        self.end()
    def guide(self):
        self.page('How to use this book','', 'guide')
        self.txt(40,66,'Find the look. Then choose the details.',27,INK,'bold')
        self.para(40,111,'Every concept has a stable number. Start with the six overview pages, then open the individual sheets for a closer comparison.',710,12)
        for idx,(title,note) in enumerate(FAMILIES):
            x=40+(idx%2)*390;y=180+(idx//2)*84
            self.txt(x,y,f'{idx*6+1:02d}-{idx*6+6:02d}  {title}',14,INK,'bold')
            self.para(x,y+24,note,345,10.5)
            self.c.linkRect('',f'family-{idx}',(x,PH-y-66,x+350,PH-y),relative=0,thickness=0)
        self.rule(441)
        self.para(40,459,'These are design mockups, not screenshots of implemented changes. The running notifier is unchanged. Color is paired with text or a symbol; completion and attention are never identified by color alone.',720,11)
        self.para(40,514,'Cards use consistent sample content. On detail pages, every logical pixel is shown at 0.75 PDF points; actual on-screen size depends on your viewer zoom and display scaling.',720,9.5)
        self.end()
    def overview(self,family):
        title,note=FAMILIES[family]
        self.page(title,bookmark=f'family-{family}')
        self.c.addOutlineEntry(title,f'family-{family}',0)
        self.txt(40,65,title,30,INK,'bold')
        self.para(40,108,note,740,12)
        for idx,st in enumerate(STYLES[family*6:family*6+6]):
            x=40+(idx%3)*260;y=166+(idx//3)*190
            self.txt(x,y,f'{st.id:02d}  {st.name}',12,INK,'bold')
            width=232
            self.preview(st,x,y+32,width,panel=False)
            self.txt(x,y+136,f'{st.width} x {st.height} px  /  {st.radius} px corners',8.5,MUTED)
            self.c.linkRect('',f'style-{st.id}',(x,PH-y-155,x+240,PH-y),relative=0,thickness=0)
        self.txt(40,544,'Click a concept to open its detail sheet. Thumbnails are normalized to the same width.',9,MUTED)
        self.end()
    def detail(self,st):
        self.page(FAMILIES[st.family][0],bookmark=f'style-{st.id}')
        self.c.addOutlineEntry(f'{st.id:02d} {st.name}',f'style-{st.id}',1)
        self.txt(40,63,f'{st.id:02d}',30,'#739085','light')
        self.txt(100,66,st.name,27,INK,'bold')
        self.txt(40,110,f'{st.width} x {st.height} logical px   /   {st.radius} px corner radius   /   {st.layout.replace("toprule","top rule").replace("accenttype","accent title")} layout',10,MUTED)
        width=st.width*.75
        # The wide-strip concept is displayed once per row to retain the same scale.
        if st.width>500:
            self.txt(40,149,'COMPLETION',9,MUTED,'bold');self.preview(st,40,174,width,panel=False)
            self.txt(40,267,'ATTENTION',9,MUTED,'bold');self.preview(st,40,292,width,state='attention',panel=False)
            self.txt(40,385,'LONG MESSAGE',9,MUTED,'bold');self.preview(st,40,410,width,state='long',panel=False)
            nx,ny,nw=492,166,303
        else:
            self.txt(40,151,'COMPLETION',9,MUTED,'bold')
            self.txt(432,151,'ATTENTION',9,MUTED,'bold')
            self.preview(st,40,179,width,panel=False)
            self.preview(st,432,179,width,state='attention',panel=False)
            self.txt(40,350,'LONG MESSAGE / OVERFLOW',9,MUTED,'bold')
            self.preview(st,40,378,width,state='long',panel=False)
            nx,ny,nw=432,348,356
        self.txt(nx,ny,'WHY CHOOSE IT',9,INK,'bold')
        end=self.para(nx,ny+21,st.why,nw,10.5)
        self.txt(nx,end+15,'TRADEOFF',9,INK,'bold')
        end=self.para(nx,end+35,st.tradeoff,nw,10.5)
        yy=end+19
        for i,(label,col) in enumerate([('Surface',st.bg),('Text',st.fg),('Accent',st.accent)]):
            xx=nx+i*(nw/3)
            self.box(xx,yy,14,14,col,3,LINE)
            self.txt(xx+20,yy,label,8,MUTED)
            self.txt(xx+20,yy+13,col.upper(),7.5,MUTED,'mono')
        self.end()
    def comparison(self,attention=False):
        self.page('Compare in context',bookmark='attention-comparison' if attention else 'desktop-comparison')
        self.c.addOutlineEntry('Attention comparison' if attention else 'Desktop comparison','attention-comparison' if attention else 'desktop-comparison',0)
        self.txt(40,64,'The same message, four directions.' if attention else 'See the card against a desktop.',27,INK,'bold')
        self.para(40,109,'Compare the attention state at an equal scale. The surface, layout, and labeling stay consistent with each concept.' if attention else 'Simplified dark and light desktop backdrops reveal how much separation each treatment creates. These are illustrative backgrounds.',720,11.5)
        picks=[STYLES[i-1] for i in ([1,11,13,31] if attention else [2,7,25,34])]
        for j,st in enumerate(picks):
            x=40+(j%2)*391;y=163+(j//2)*183
            self.txt(x,y,f'{st.id:02d}  {st.name}',11,INK,'bold')
            self.box(x,y+25,369,140,'#343C45' if j%2==0 else '#E2E7E8',8)
            self.preview(st,x+12,y+38,345,state='attention' if attention else 'completion',panel=False)
        self.end()
    def shortlist(self):
        self.page('A starting shortlist',bookmark='shortlist')
        self.c.addOutlineEntry('A starting shortlist','shortlist',0)
        self.txt(40,65,'Six places to start.',29,INK,'bold')
        self.para(40,109,'These are subjective design picks, based on your request for something sleek, minimal, and slightly more polished.',720,11.5)
        rows=[(1,'Closest to what you have','Keeps the familiar dark card and makes the smallest visual step.'),
              (2,'Most restrained','A plain text-led dark surface with very little visual decoration.'),
              (7,'Cleanest light direction','A neutral light card with a clear title and a tiny status marker.'),
              (13,'Best starting point for compact','A short card with a narrow accent and a readable hierarchy.'),
              (25,'Gentlest color treatment','A muted sage surface adds personality without saturation.'),
              (31,'My first alternative to compare','The full-height card gains one crisp accent without extra UI elements.')]
        for j,(id,label,note) in enumerate(rows):
            y=169+j*56
            self.txt(40,y,f'{id:02d}',20,'#617F73','bold')
            self.txt(88,y,label,12,INK,'bold')
            self.txt(88,y+22,note,10.5,MUTED)
            self.c.linkRect('',f'style-{id}',(40,PH-y-44,PW-40,PH-y),relative=0,thickness=0)
        self.end()
    def worksheet(self):
        self.page('Choose a direction',bookmark='choice')
        self.c.addOutlineEntry('Your selection','choice',0)
        self.txt(40,65,'Your shortlist.',30,INK,'bold')
        self.para(40,113,'Choose one complete concept, or combine a small number of details. The concept number is enough to identify a starting point.',720,12)
        for i,t in enumerate(['First choice','Second choice','Third choice']):
            x=40+i*260
            self.box(x,177,239,87,'#FFFFFF',8,LINE)
            self.txt(x+16,191,t.upper(),9,MUTED,'bold')
            self.txt(x+16,223,'Concept #',13,INK)
            self.box(x+91,243,129,.7,LINE)
        self.txt(40,296,'If you want a combination',16,INK,'bold')
        for i,t in enumerate(['Layout from #','Colors from #','Status marker from #','Card size / spacing']):
            x=40+(i%2)*390;y=337+(i//2)*65
            self.txt(x,y,t,11,INK)
            self.box(x,y+34,350,.7,LINE)
        self.box(40,480,760,56,'#E9F0EC',8)
        self.txt(56,493,'Example: "Use #31, with #7\'s light colors and #13\'s shorter height."',12,INK)
        self.txt(56,517,'All 108 card previews, all 48 page images, and the Python source are retained alongside this PDF.',9,MUTED)
        self.end()
    def build(self):
        self.cover();self.guide()
        for family in range(6):
            self.overview(family)
            for st in STYLES[family*6:family*6+6]:self.detail(st)
        self.comparison();self.comparison(True);self.shortlist();self.worksheet()
        assert self.n==48,self.n
        self.c.save()


def verify_and_render():
    PAGES.mkdir(parents=True,exist_ok=True)
    doc=fitz.open(PDF)
    assert len(doc)==48
    links=[link for page in doc for link in page.get_links()]
    assert len(links)==48
    page_refs={doc.page_xref(i) for i in range(len(doc))}
    for link in links:
        # Check the actual PDF destination, including /Fit destinations that
        # some PyMuPDF versions expose as LINK_NAMED with a one-based page.
        kind,dest=doc.xref_get_key(link['xref'],'Dest')
        ref=re.match(r'\[\s*(\d+)\s+0\s+R',dest)
        assert kind=='array' and ref and int(ref.group(1)) in page_refs,dest
    assert len(doc.get_toc())==47
    assert '\ufffd' not in '\n'.join(page.get_text() for page in doc)
    for idx,page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            if block['type']!=0:continue
            for line in block['lines']:
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    assert x0>=0 and y0>=0 and x1<=PW+1 and y1<=PH+1,(idx+1,span['text'])
        page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(PAGES/f'page-{idx+1:02d}.png')
    # Retain overview sheets of the rendered PDF for rapid visual QA.
    for start in range(0,len(doc),12):
        sheet=Image.new('RGB',(4*421,3*320),'#DCE2E5')
        draw=ImageDraw.Draw(sheet)
        for offset in range(min(12,len(doc)-start)):
            im=Image.open(PAGES/f'page-{start+offset+1:02d}.png').convert('RGB')
            im.thumbnail((409,289),Image.Resampling.LANCZOS)
            xx=(offset%4)*421+6;yy=(offset//4)*320+6
            sheet.paste(im,(xx,yy))
            draw.text((xx,yy+292),f'Page {start+offset+1:02d}',fill='#203039')
        sheet.save(OUT/f'page-overview-{start//12+1}.png')
    summary={'pages':len(doc),'concepts':len(STYLES),'card_previews':len(list(PREVIEWS.glob('*.png'))),
             'pdf_bytes':PDF.stat().st_size,'text_bounds':'passed',
             'verified_navigation_links':len(links),'bookmarks':len(doc.get_toc()),
             'pdf':str(PDF),'rendered_pages':str(PAGES)}
    (OUT/'verification.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (OUT/'README.md').write_text(
        '# Notification style lookbook\n\n'
        'These are retained design deliverables. Keep the PDF, images, and source.\n\n'
        '- Main document: `../pdf/codex-notify-style-lookbook.pdf` (48 pages).\n'
        '- `previews/`: 108 transparent PNGs, three states for each of 36 concepts.\n'
        '- `pages/`: all 48 PDF pages rendered as PNGs.\n'
        '- `page-overview-*.png`: visual contact sheets of the PDF pages.\n'
        '- `styles.json`: colors, sizes, layouts, and design notes.\n'
        '- `build_lookbook.py`: reproducible Python renderer and PDF builder.\n\n'
        'The images are proposed designs, not captured screenshots of the running app. '
        'The app was not changed by this design study.\n\n'
        'Rebuild from the repo root with:\n\n'
        '```powershell\n'
        "& 'C:/Users/lemondoo/AppData/Local/Programs/Python/Python311/python.exe' "
        "'output/notification-styles/build_lookbook.py'\n```\n",
        encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    save_previews()
    Book().build()
    verify_and_render()
