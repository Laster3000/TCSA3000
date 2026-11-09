#!/usr/bin/env python3
"""Read-only search for isolated historic catalog and original LISTA.
This tool does not import archived authority, execute code or change sources.
"""
import argparse, gzip, json, os, pathlib, zipfile
DEFAULT=pathlib.Path(os.environ.get("TCSA_ROOT",r"G:\Mi unidad\TCSA"))
def query_archive(root,term,limit=20,include_content=False):
    hist=root/"09-HISTORICO"
    q=term.casefold()
    found=[]
    paths=hist/"CATALOGO-FICHEROS-LEGADO.jsonl.gz"
    with gzip.open(paths,"rt",encoding="utf-8") as f:
        for line in f:
            x=json.loads(line)
            if q in x["path"].casefold():
                found.append({"kind":"HISTORICAL_PATH","path":x["path"],"bytes":x["size"]})
                if len(found)>=limit:return found
    lista=hist/"LISTA-ANTIGUA-MMC"/"LISTA-ORIGINAL-ARCHIVO.zip"
    if not lista.exists():
        lista=hist/"LISTA-ORIGINAL-ARCHIVO.zip"  # lectura de archivos anteriores a la segregación
    if lista.exists():
        with zipfile.ZipFile(lista) as z:
            for name in z.namelist():
                if not name.lower().endswith((".md",".txt",".json")):continue
                match=q in name.casefold()
                snippet=""
                if include_content and not match:
                    info=z.getinfo(name)
                    if info.file_size<=1024*1024:
                        text=z.read(name).decode("utf-8",errors="replace")
                        pos=text.casefold().find(q)
                        if pos>=0:
                            match=True; snippet=text[max(0,pos-70):pos+160].replace("\n"," ")
                if match:
                    found.append({"kind":"HISTORICAL_LISTA","path":name,"snippet":snippet,"status":"REFERENCE_ONLY"})
                if len(found)>=limit:break
    return found
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=pathlib.Path,default=DEFAULT)
    p.add_argument("--query",required=True)
    p.add_argument("--limit",type=int,default=20)
    p.add_argument("--include-content",action="store_true")
    a=p.parse_args()
    results=query_archive(a.root,a.query,max(1,min(a.limit,100)),a.include_content)
    print(json.dumps({"query":a.query,"results":results,"authority":"KNOWLEDGE_ONLY","note":"Historical data never changes active project status"},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
