"""Deterministic candidates and pre-implementation checks; never aesthetic approval."""
import colorsys
import re

def forbidden_color(value):
    # Runtime collection converts modern CSS colors to sRGB. Source scanning also
    # recognizes common legacy forms, including shorthand and alpha hex.
    pattern=r'#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{4}\b|#[0-9a-fA-F]{3}\b|(?:rgba?|hsla?)\([^)]*\)|\b(?:purple|indigo|violet|blueviolet|rebeccapurple|mediumpurple|darkviolet|darkorchid)\b'
    names={'purple','indigo','violet','blueviolet','rebeccapurple','mediumpurple','darkviolet','darkorchid'}
    for token in re.findall(pattern,str(value),re.I):
        token=token.lower()
        if token in names:return True
        if token.startswith('#'):
            raw=token[1:]
            if len(raw) in (3,4):raw=''.join(char*2 for char in raw)
            if len(raw)==8 and int(raw[6:8],16)==0:continue
            h,s,_=colorsys.rgb_to_hsv(*(int(raw[i:i+2],16)/255 for i in (0,2,4)))
            h*=360
        else:
            values=re.findall(r'-?\d*\.?\d+(?:e[-+]?\d+)?(?:%|deg|turn|rad|grad)?',token)
            if len(values)<3:continue
            number=lambda text:float(re.match(r'-?[\d.e+\-]+',text)[0])
            if len(values)>3 and number(values[3])==0:continue
            if token.startswith('hsl'):
                hue=values[0];h=number(hue)
                if hue.endswith('turn'):h*=360
                elif hue.endswith('grad'):h*=.9
                elif hue.endswith('rad'):h*=180/3.141592653589793
                h%=360;s=number(values[1])/100
            else:
                h,s,_=colorsys.rgb_to_hsv(*(number(v)/(100 if v.endswith('%') else 255) for v in values[:3]));h*=360
        if 230<=h<=300 and s>=.15:return True
    return False

def forbidden_easing(value):
    value=re.sub(r'\s+','',str(value).lower())
    if value in ('linear','ease-in-out'):return True
    match=re.fullmatch(r'cubic-bezier\(([-+.\d]+),([-+.\d]+),([-+.\d]+),([-+.\d]+)\)',value)
    if match:
        x1,y1,x2,y2=map(float,match.groups())
        return (abs(x1-y1)<1e-8 and abs(x2-y2)<1e-8) or (x1,y1,x2,y2)==(.42,0,.58,1)
    return False

def rendered_candidates(snapshot):
    failures=[];gaps=[]
    for item in snapshot.get('normalized_colors',[]):
        if forbidden_color(item['value']):failures.append('rendered forbidden color: '+item['selector']+' '+item['property'])
    for region in snapshot.get('layout_regions',[]):
        # Clear equal-column geometry is a candidate, never a beauty score.
        children=[x for x in region.get('children',[]) if x.get('width',0)>20 and x.get('height',0)>0]
        if len(children)>=2 and region.get('display') in ('grid','flex'):
            if max(x['y'] for x in children)-min(x['y'] for x in children)<=2 and max(x['width'] for x in children)-min(x['width'] for x in children)<=1 and all(x.get('tag') not in ('input','svg','path','img') for x in children):
                failures.append('equal-width column candidate: '+region['selector'])
    # The document surface is a candidate; unusual canvas/SVG/background layers
    # require inspection, and cannot be certified from absence of a CSS gradient.
    surface=snapshot.get('surface',{})
    document_surface=surface.get('scope')=='document' or ('scope' not in surface and snapshot.get('root_selector','body') in ('body','html'))
    candidates=[item for item in surface.get('material_candidates',[]) if item.get('visible',True) and item.get('effective_opacity',1)>0]
    if surface and document_surface and not candidates:
        gaps.append('Page background texture/gradient not demonstrated; inspect document and background layers')
    boundaries=snapshot.get('boundaries',{})
    if boundaries.get('iframes') or boundaries.get('possible_closed_roots'):
        gaps.append('Uninspected iframe/closed-shadow boundary; collect separate evidence for its affected content')
    return failures,gaps

def delivery_declarations(message):
    values=re.findall(r'(?:最终状态|验收状态|Final status|Status)\s*[:：]\s*(PASS|FAIL|BLOCKED)\b',message,re.I)
    return [value.upper() for value in values]

def contradictory_delivery(message,status):
    if status=='PASS':return False
    for sentence in re.split(r'[。！？!\n]',message):
        if re.search(r'未|不|不能|无法|尚|禁止|不得|没有|not\b|cannot|never',sentence,re.I):continue
        if re.search(r'全部(?:落实|通过|完成)|完整(?:落实|通过验收)|完全(?:落实|合规)|所有.{0,6}(?:已通过|已解决)|all\s+(?:checks|requirements)\s+(?:have\s+)?passed|fully\s+(?:compliant|verified)',sentence,re.I):return True
    return False
