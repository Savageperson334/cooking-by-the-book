/* BakeLab: Pyodide 314 requires ES module workers (classic importScripts is unsupported).
 * The runtime is imported dynamically so that a failed CDN download is reported
 * with a readable message instead of a generic worker error. */
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs';
let pyodide;
let model;
let latestId = 0;
const ready = (async () => {
  let loadPyodide;
  try {
    ({ loadPyodide } = await import(PYODIDE_URL));
  } catch (error) {
    throw Error('Could not download the Python runtime (Pyodide) from cdn.jsdelivr.net. Check your internet connection, then reload the page.');
  }
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
  latestId = Math.max(latestId, id);
  try {
    await ready;
    // Let any run requests queued behind a long simulation arrive first, then
    // solve only the newest one. The app already ignores superseded results.
    await new Promise(resolve => setTimeout(resolve, 15));
    if (id !== latestId) return;
    const output = model(JSON.stringify(payload));
    self.postMessage({id,type:'result',result:JSON.parse(output)});
  } catch (error) {
    // Initialization failures are reported once below, without an id.
    if (!model) return;
    self.postMessage({id,type:'error',error:String(error?.message || error)});
  }
};
ready.catch(error => self.postMessage({type:'error',error:'Python initialization failed: '+String(error?.message||error)}));
