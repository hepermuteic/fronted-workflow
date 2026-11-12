"""Read StyleKit through its pinned official CLI without changing project files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

def fetch_document(slug,locale):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):raise ValueError('Invalid StyleKit slug')
    locales={'zh':'zh','zh-CN':'zh','en':'en'}
    if locale not in locales:raise ValueError('Supported page languages are zh, zh-CN and en')
    language=locales[locale]
    url='https://www.stylekit.top/api/design/'+slug+'/design.md?locale='+language
    request=urllib.request.Request(url,headers={'Accept':'text/markdown','User-Agent':'frontend-workflow/4.1'})
    with urllib.request.urlopen(request,timeout=25) as response:
        data=response.read(2_000_001)
    if len(data)>2_000_000:raise ValueError('Style document exceeds size limit')
    text=data.decode('utf-8-sig')
    if not text.lstrip().startswith('# ') or '<html' in text[:500].lower():raise ValueError('StyleKit returned an invalid Markdown document')
    if 'Implementation Contract' not in text:raise ValueError('Complete Implementation Contract is missing')
    if language=='zh' and not re.search(r'[\u4e00-\u9fff]',text):raise ValueError('Requested Chinese document returned another language')
    return text,{'slug':slug,'locale':language,'source_url':url,'sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'fetched_at':datetime.now(timezone.utc).isoformat()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('query',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    if args.query and args.query[0]=='document':
        document_parser=argparse.ArgumentParser(description='Fetch the complete selected-language design document')
        document_parser.add_argument('slug')
        document_parser.add_argument('--locale',choices=['zh','zh-CN','en'],required=True)
        document_args=document_parser.parse_args(args.query[1:])
        if not args.output:parser.error('document requires --output before the document command')
        text,metadata=fetch_document(document_args.slug,document_args.locale)
        target=Path(args.output)
        if target.exists() and target.read_text(encoding='utf-8')!=text:raise ValueError('Existing style document differs; use a versioned output path')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding='utf-8',newline='')
        print(json.dumps({**metadata,'path':str(target),'status':'PASS','scope':'Complete language-specific style source retrieved'},ensure_ascii=False))
        return 0
    allowed={'list','search','show','tokens','recipe','brief','assets','asset','add'}
    if not args.query or args.query[0] not in allowed:parser.error('Use a read-only StyleKit query command')
    package=Path.home()/'.codex/frontend-policy/tooling/node_modules/stylekit-cli'
    metadata=json.loads((package/'package.json').read_text(encoding='utf-8'))
    if metadata['version']!='0.3.1':parser.error('Install the verified stylekit-cli@0.3.1 runtime')
    binaries=metadata['bin']
    entry=binaries if isinstance(binaries,str) else next(iter(binaries.values()))
    node=shutil.which('node')
    if not node:parser.error('Node is unavailable')
    command=[node,str(package/entry),*args.query]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
    output={'tool':'stylekit-cli','version':metadata['version'],'command':args.query,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    try:output['data']=json.loads(result.stdout)
    except ValueError:pass
    text=json.dumps(output,ensure_ascii=False,indent=2)
    if args.output:
        target=Path(args.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding='utf-8')
    else:print(text)
    return result.returncode

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status':'BLOCKED','error':str(exc)},ensure_ascii=False))
        raise SystemExit(2)
