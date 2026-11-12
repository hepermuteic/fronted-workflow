"""Discovery contracts and actual Motion/GSAP pointer behavior."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_release import p, plan

class V4Tests(unittest.TestCase):
    def test_named_style_labels_are_required_for_new_directions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_text('Fixture')
            task=plan(root,level='L3')
            discovery=p.load(root/'discovery.json')
            discovery['options'][0].pop('style_name')
            p.save(root/'discovery.json',discovery)
            self.assertTrue(any('style_name' in gap for gap in p.preflight.discovery_gaps(p,root,task)))

    def test_palette_only_directions_are_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_text('Fixture')
            task=plan(root,level='L3')
            discovery=p.load(root/'discovery.json')
            for option in discovery['options']:
                for key in ('layout','typography','components','material','imagery'):option[key]='same'
                option['palette']=option['id']
            p.save(root/'discovery.json',discovery)
            self.assertTrue(any('repeat' in x for x in p.preflight.discovery_gaps(p,root,task)))

    def test_pointer_routing_cannot_be_omitted_from_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_text('Fixture')
            task=plan(root,level='L3')
            task['design_plan'].pop('motion_plan')
            self.assertTrue(any('pointer adoption' in x for x in p.preflight.discovery_gaps(p,root,task)))

    def test_actual_motion_gsap_pointer_and_reduced_motion(self):
        tooling=Path.home()/'.codex/frontend-policy/tooling/node_modules'
        node=shutil.which('node')
        with tempfile.TemporaryDirectory(prefix='frontend-v4-') as folder:
            root=Path(folder)
            jsx='''import React from 'react';
import {createRoot} from 'react-dom/client';
import {motion,useSpring,useReducedMotion} from 'motion/react';
import {gsap} from 'gsap';
function Probe(){
 const reduced=useReducedMotion();
 const x=useSpring(0,{stiffness:300,damping:30});
 return <><motion.button id="motion" style={{x:reduced?0:x}} onPointerMove={()=>{if(!reduced)x.set(24)}} onPointerLeave={()=>x.set(0)}>Motion</motion.button><button id="gsap" onPointerMove={e=>{if(!matchMedia('(prefers-reduced-motion: reduce)').matches)gsap.quickTo(e.currentTarget,'x',{duration:.15,ease:'expo.out'})(24)}}>GSAP</button><output id="mode">{reduced?'reduce':'normal'}</output></>;
}createRoot(document.getElementById('root')).render(<Probe/>);'''
            options={'stdin':{'contents':jsx,'resolveDir':str(tooling.parent),'loader':'jsx'},'bundle':True,'outfile':str(root/'app.js'),'nodePaths':[str(tooling)]}
            result=subprocess.run([node,'-e',"require(process.argv[1]).buildSync(JSON.parse(process.argv[2]))",str(tooling/'esbuild'),json.dumps(options)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            (root/'index.html').write_text('<meta charset="utf-8"><style>html{font-family:Arial,SimSun,serif}body,input,button,textarea,select{font-family:inherit}body{min-height:100vh;background:linear-gradient(20deg,#f4f1e7,#ede8dc)}button{display:block;margin:35px;padding:20px}</style><div id="root"></div><script src="app.js"></script>',encoding='utf-8')
            task=plan(root)
            task['files'].append('app.js')
            task['scope'].append({'page':'main','width':390,'state':'reduce'})
            p.save(root/p.TASK_PATH,task)
            steps=[]
            for selector in ('#motion','#gsap'):
                steps += [{'action':'remember_style','selector':selector,'property':'transform','name':selector},{'action':'move_pointer','selector':selector,'x_ratio':.6,'y_ratio':.5},{'action':'expect_style_changed','selector':selector,'name':selector}]
            reduced=[{'action':'expect_text','selector':'#mode','value':'reduce'}]
            for selector in ('#motion','#gsap'):
                reduced += [{'action':'remember_style','selector':selector,'property':'transform','name':selector},{'action':'hover','selector':selector},{'action':'expect_style_unchanged','selector':selector,'name':selector}]
            p.save(root/'spec.json',{'cases':[{'page':'main','width':390,'state':'default','url':(root/'index.html').as_uri(),'steps':steps},{'page':'main','width':390,'state':'reduce','reduced_motion':'reduce','url':(root/'index.html').as_uri(),'steps':reduced}]})
            record=p.run_browser(root,'spec.json')
            self.assertEqual(record['status'],'PASS',record.get('runner_error'))
            self.assertEqual(len(record['assertions']),2)
            self.assertEqual(record['assertions'][0]['passed'],2)

if __name__=='__main__':unittest.main()
