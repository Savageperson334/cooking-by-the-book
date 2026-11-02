/* Python simulation runs in a web worker, leaving all sliders responsive. */
let pyodide;
let model;
const ready = (async () => {
  importScripts('https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js');
  pyodide = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'});
  const source = await fetch('./engine.py').then(r => { if(!r.ok)throw Error('Cannot load engine.py');return r.text(); });
  pyodide.FS.writeFile('/home/pyodide/engine.py',source);
  pyodide.runPython('import sys;sys.path.insert(0,"/home/pyodide");import engine');
  model = pyodide.globals.get('engine').simulate_json;
  self.postMessage({type:'ready'});
})();
self.onmessage = async (event) => {
  const {id,payload} = event.data;
  try {
    await ready;
    const output = model(JSON.stringify(payload));
    self.postMessage({id,type:'result',result:JSON.parse(output)});
  } catch (error) {
    self.postMessage({id,type:'error',error:String(error?.message || error)});
  }
};
ready.catch(e=>self.postMessage({type:'error',error:'Python initialization failed: '+String(e?.message||e)}));
