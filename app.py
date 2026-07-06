import os, json, tempfile
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
import markdown as md_lib
from scoring import score_csv
from coach import build_markdown

app = FastAPI()

PAGE = """
<!doctype html><html><head><meta charset="utf-8">

<title>Quantitative Coach</title>

<style>

 :root{--ink:#1a2440;--accent:#2f5bd0;--line:#dfe5f1;--bg:#f5f7fc}

 *{box-sizing:border-box}

 body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);

      background:var(--bg);margin:0;line-height:1.6}

 header{background:#fff;border-bottom:1px solid var(--line);padding:20px 24px}

 header h1{margin:0;font-size:1.3rem}

 header p{margin:4px 0 0;color:#667;font-size:.9rem}

 .wrap{max-width:840px;margin:32px auto;padding:0 20px}

 .card{background:#fff;border:1px solid var(--line);border-radius:14px;

       padding:28px;box-shadow:0 1px 3px rgba(20,40,90,.05)}

 .drop{border:2px dashed #c4cfe6;border-radius:12px;padding:34px;text-align:center}

 input[type=file]{margin-bottom:14px}

 button{background:var(--accent);color:#fff;border:0;border-radius:9px;

        padding:11px 24px;font-size:1rem;font-weight:600;cursor:pointer}

 button:disabled{opacity:.5;cursor:default}

 #progress{display:none;margin-top:22px}

 .track{height:14px;background:#e7ecf7;border-radius:8px;overflow:hidden}

 .fill{height:100%;width:0;background:var(--accent);transition:width .3s ease}

 #ptext{font-size:.9rem;color:#556;margin-top:8px;text-align:center}

 /* report styling */

 .report{background:#fff;border:1px solid var(--line);border-radius:14px;

         padding:32px 36px;margin-top:26px;box-shadow:0 1px 3px rgba(20,40,90,.05)}

 .report h1{font-size:1.5rem;margin:.2em 0 .6em;border-bottom:2px solid var(--line);padding-bottom:.3em}

 .report h2{font-size:1.18rem;margin:1.4em 0 .5em;color:var(--accent)}

 .report h3{font-size:1.03rem;margin:1.1em 0 .4em}

 .report table{border-collapse:collapse;width:100%;margin:14px 0}

 .report th,.report td{border:1px solid var(--line);padding:9px 13px;text-align:left}

 .report th{background:#eef2fb}

 .report ul{margin:.4em 0 1em;padding-left:1.3em}

 .report li{margin:.3em 0}

 .report a{color:var(--accent);word-break:break-all}

 .report strong{color:var(--ink)}

</style></head>

<body>

<header><h1>Quantitative Coach</h1><p>Upload a results export to generate student reports.</p></header>

<div class="wrap">

 <div class="card">

   <div class="drop">

     <div><input type="file" id="file" accept=".csv"></div>

     <button id="go" onclick="run()">Generate Reports</button>

   </div>

   <div id="progress">

     <div class="track"><div class="fill" id="fill"></div></div>

     <div id="ptext">Starting…</div>

   </div>

 </div>

 <div id="results"></div>

</div>

<script>

async function run(){

  const f = document.getElementById('file').files[0];

  if(!f){ alert('Choose a .csv file first'); return; }

  const btn=document.getElementById('go'); btn.disabled=true;

  document.getElementById('progress').style.display='block';

  document.getElementById('results').innerHTML='';

  const fd=new FormData(); fd.append('file',f);

  const resp=await fetch('/generate',{method:'POST',body:fd});

  const reader=resp.body.getReader(); const dec=new TextDecoder(); let buf='';

  while(true){

    const {done,value}=await reader.read(); if(done) break;

    buf+=dec.decode(value,{stream:true});

    let lines=buf.split('\\n'); buf=lines.pop();

    for(const line of lines){

      if(!line.trim()) continue;

      const m=JSON.parse(line);

      if(m.type==='progress'){

        const pct=Math.round(100*m.done/m.total);

        document.getElementById('fill').style.width=pct+'%';

        document.getElementById('ptext').textContent='Generating… student '+m.done+' of '+m.total;

      } else if(m.type==='done'){

        document.getElementById('ptext').textContent='Done — '+m.total+' reports.';

        document.getElementById('results').innerHTML=m.html;

      }

    }

  }

  btn.disabled=false;

}

</script>

</body></html>

"""

@app.get("/", response_class=HTMLResponse)

def home():
    return PAGE
@app.post("/generate")

async def generate(file: UploadFile = File(...)):
    data = await file.read()
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    def stream():
        try:
            students = score_csv(path)
            total = len(students)
            blocks = []
            for i, s in enumerate(students, 1):
                html = md_lib.markdown(build_markdown(s), extensions=["tables", "fenced_code"])
                blocks.append(f"<div class='report'>{html}</div>")
                yield json.dumps({"type": "progress", "done": i, "total": total}) + "\n"
            yield json.dumps({"type": "done", "total": total, "html": "".join(blocks)}) + "\n"
        finally:
            os.unlink(path)
    return StreamingResponse(stream(), media_type="application/x-ndjson")
