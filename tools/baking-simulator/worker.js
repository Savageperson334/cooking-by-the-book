/* BakeLab: Pyodide 314 requires ES module workers (classic importScripts is unsupported). */
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs';
let pyodide;
let model;
const ready = (async () => {
  pyodide = await loadPyodide();
  const [response, liquidResponse, breakdownResponse, fractureResponse] = await Promise.all([fetch('./engine.py'), fetch('./liquids.py'), fetch('./thermal_breakdown.py'), fetch('./physical_fracture.py')]);
  if (!response.ok) throw Error('Cannot load engine.py');
  if (!liquidResponse.ok) throw Error('Cannot load liquids.py');
  if (!breakdownResponse.ok) throw Error('Cannot load thermal_breakdown.py');
  if (!fractureResponse.ok) throw Error('Cannot load physical_fracture.py');
  pyodide.FS.writeFile('/home/pyodide/liquids.py', await liquidResponse.text());
  pyodide.FS.writeFile('/home/pyodide/thermal_breakdown.py', await breakdownResponse.text());
  pyodide.FS.writeFile('/home/pyodide/physical_fracture.py', await fractureResponse.text());
  pyodide.FS.writeFile('/home/pyodide/engine.py', await response.text());
  pyodide.runPython('import sys;sys.path.insert(0,"/home/pyodide");import engine');
  model = pyodide.globals.get('engine').simulate_json;
  self.postMessage({type:'ready'});
})();
self.onmessage = async ({data}) => {
  const {id,payload} = data;
  try {
    await ready;
    const output = model(JSON.stringify(payload));
    self.postMessage({id,type:'result',result:JSON.parse(output)});
  } catch (error) {
    self.postMessage({id,type:'error',error:String(error?.message || error)});
  }
};
ready.catch(error => self.postMessage({type:'error',error:'Python initialization failed: '+String(error?.message||error)}));
