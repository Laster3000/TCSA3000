# coding: utf-8
"""TCSA R2: targeted read-only continuity recovery. No replay, no network.
Usage: python REANUDAR-PROYECTO.py --project-id TCSA-CORE
       python REANUDAR-PROYECTO.py --self-test
"""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/"02-CATALOGO"/"PROYECTOS.json"

class IntegrityError(RuntimeError):pass

def sha(blob):return hashlib.sha256(blob).hexdigest()
def read(p):return json.loads(p.read_text("utf-8-sig"))
def ensure_inside(path):
 p=ROOT/path
 if path.is_absolute() or ".." in path.parts or not p.resolve().is_relative_to(ROOT.resolve()):
  raise IntegrityError("PATH_ESCAPE_OR_UNTRUSTED")
 return p

def validate_checkpoint(latest_file):
 latest=read(latest_file)
 cpfile=latest_file.parent/(latest["checkpointId"]+".json")
 if not cpfile.is_file() or sha(cpfile.read_bytes())!=latest["checkpointSha256"]:
  raise IntegrityError("LATEST_POINTER_SHA_MISMATCH")
 doc=read(cpfile)
 if doc.get("snapshotStatus")!="COMMITTED":
  raise IntegrityError("LAST_CHECKPOINT_NOT_COMMITTED")
 prev=doc.get("prevSha256")
 if prev!=latest.get("prevSha256"):
  raise IntegrityError("PREVIOUS_HASH_LINK_DISAGREEMENT")
 if "payloadSha256" in doc:
  canonical=(json.dumps(doc["payload"],ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
  if sha(canonical)!=doc["payloadSha256"]:
   raise IntegrityError("CHECKPOINT_PAYLOAD_SHA_MISMATCH")
 # Only the chosen project's folder (typically 4 entries). Not a global TCSA scan.
 existing={sha(p.read_bytes()):(p,read(p)) for p in latest_file.parent.glob("*.json") if p.name!="LATEST.json"}
 visited=[]
 link=latest["checkpointSha256"]
 while link:
  if link not in existing:
   raise IntegrityError("BROKEN_OR_MISSING_CHECKPOINT_ANCESTOR")
  if link in visited:
   raise IntegrityError("CYCLIC_CHECKPOINT_CHAIN")
  visited.append(link)
  link=existing[link][1].get("prevSha256")
 return latest,doc,len(visited)

def pending_intents(cpdir):
 opdir=cpdir/"OPERACIONES"
 pending=[]
 confirmed=[]
 if not opdir.is_dir():return pending,confirmed
 for p in opdir.glob("*.intent.json"):
  doc=read(p)
  label=p.name.replace(".intent.json","")
  receipt=opdir/(label+".commit.json")
  if receipt.is_file():
   status=read(receipt)
   if status.get("operationId")!=doc.get("operationId") or not status.get("state","").startswith("SUCCEEDED"):
    pending.append({"operationId":doc.get("operationId"),"status":"UNKNOWN_RECONCILE_BAD_COMMIT"})
   else:
    confirmed.append(doc.get("operationId"))
  else:
   pending.append({"operationId":doc.get("operationId"),"status":"UNKNOWN_INTENT_WITHOUT_COMMIT"})
 return pending,confirmed

def retrieve(project_id):
 catalog=read(CATALOG)
 matches=[p for p in catalog["projects"] if p["projectId"]==project_id]
 if len(matches)!=1:raise IntegrityError("PROJECT_ID_MISSING_OR_AMBIGUOUS")
 summary=matches[0]
 capsule_ref=summary.get("capsule")
 if not capsule_ref and project_id=="TCSA-CORE":
  # The preexisting TCSA catalog entry omitted the capsule key.
  capsule_ref="03-PROYECTOS/TCSA-CORE/CAPSULA-PROYECTO.json"
 capsule=read(ensure_inside(Path(capsule_ref))) if capsule_ref else {}
 result={"schema":"tcsa.targeted-resume.v1","projectId":project_id,
  "catalogIsLive":False,"status":summary.get("status"),"displayStatus":summary.get("displayStatus"),
  "capsuleRevisionId":capsule.get("revisionId"),
  "noAutomaticExecution":True,"realExecutorState":"NOT_QUERIED_NEEDS_LIVE_READBACK"}
 if project_id!="TCSA-CORE":
  # Targeted verification only for the selected project. No global crawl.
  result["nextAction"]=capsule.get("nextAction")
  latest_ref=summary.get("latestEvidenceCheckpoint") or capsule.get("latestVerifiedCheckpoint")
  receipt_ref=summary.get("latestEvidenceReceipt") or capsule.get("latestEvidenceReceipt")
  if not latest_ref:
   result["resumeReadiness"]="UNKNOWN_GAP_NO_PROJECT_CHECKPOINT_POINTER"
   result["warnings"]=["No checkpoint pointer in catalog/capsule. Preserve previous sessions and search only this project's authorized sources."]
   return result
  checkpoint=ensure_inside(Path(latest_ref))
  if not checkpoint.is_file():raise IntegrityError("PROJECT_CHECKPOINT_MISSING")
  if not receipt_ref:
   result["resumeReadiness"]="PARTIAL_CHECKPOINT_EXISTS_BUT_NO_RECEIPT"
   result["checkpointPointer"]=latest_ref
   return result
  evidence=read(ensure_inside(Path(receipt_ref)))
  stored=evidence.get("checkpoints",{})
  checked=[]
  for rel in [latest_ref,capsule.get("latestConversationCheckpoint"),capsule.get("latestExecutorCheckpoint")]:
   if not rel:continue
   p=ensure_inside(Path(rel))
   expected=stored.get(p.name)
   if not expected:
    raise IntegrityError("CHECKPOINT_RECEIPT_HASH_NOT_FOUND:"+p.name)
   if not p.is_file() or sha(p.read_bytes())!=expected:
    raise IntegrityError("CHECKPOINT_MISSING_OR_SHA_DRIFT:"+p.name)
   checked.append({"path":rel,"sha256":expected})
  result["resumeReadiness"]="SCOPED_CHECKPOINTS_VERIFIED_NOT_FULL_CONVERSATION_OR_LIVE_EXECUTOR"
  result["verifiedProjectConversationExecutor"] = checked
  result["checkpointPointer"]=latest_ref
  result["unknownGaps"]=["No full conversation transcript unless separately preserved; check exact conversation and original live journal before resuming effects."]
  return result
 idxref=summary.get("continuityIndex")
 if not idxref:raise IntegrityError("CONTINUITY_INDEX_MISSING")
 index=read(ensure_inside(Path(idxref)))
 if index.get("projectId")!=project_id:raise IntegrityError("INDEX_PROJECT_ID_MISMATCH")
 latest_path=ensure_inside(Path(index["latestProjectCheckpointPointer"]))
 latest,cp,count=validate_checkpoint(latest_path)
 if index.get("newCheckpointSha256")!=latest["checkpointSha256"]:
  raise IntegrityError("INDEX_LATEST_SHA_NOT_MATCHED")
 if cp["payload"].get("revisionId")!=capsule.get("revisionId"):
  raise IntegrityError("CAPSULE_CHECKPOINT_REVISION_MISMATCH")
 if cp["payload"].get("status")!=summary.get("status"):
  raise IntegrityError("STATUS_CONTRADICTION_RECONCILE")
 records=[]
 for item in index["conversationCheckpoints"]:
  record=ensure_inside(Path(item["path"]))
  if not record.is_file() or sha(record.read_bytes())!=item["sha256"]:
   raise IntegrityError("CONVERSATION_CHECKPOINT_MISSING_OR_SHA_DRIFT")
  records.append({"path":item["path"],"coverage":item.get("coverage")})
 pending,done=pending_intents(latest_path.parent)
 result.update({
  "checkpointId":latest["checkpointId"],
  "checkpointSha256":latest["checkpointSha256"],
  "checkpointChainEntries":count,
  "priorConversationRefsVerified":len(records),
  "conversationRecords":records,
  "operationIntentsWithoutValidCommit":pending,
  "completedOperationsNotToRepeat":done,
  "readyForReadOnlyContinuation":True,
  "readyForAutomaticJobReplay":False,
  "unknownGaps":index.get("unknownGaps",[]),
  "nextAction":index.get("nextAction")
 })
 return result

def cas(path,old,new):
 if path.read_bytes()!=old:raise IntegrityError("CAS_EXPECTED_PREIMAGE_MISMATCH")
 stage=path.with_suffix(".stage")
 if stage.exists():raise IntegrityError("STAGING_CONFLICT")
 with stage.open("xb") as f:
  f.write(new);f.flush();os.fsync(f.fileno())
 if path.read_bytes()!=old:raise IntegrityError("CAS_CONCURRENT_WRITER")
 os.replace(stage,path)
 if path.read_bytes()!=new:raise IntegrityError("CAS_READBACK_MISMATCH")

def simulate():
 tests={}
 with tempfile.TemporaryDirectory(prefix="tcsa-crash-recovery-r2-") as td:
  directory=Path(td)
  pointer=directory/"LATEST.json"
  a=b'{"state":"LKG"}'
  pointer.write_bytes(a)
  # Simulated interruption after checkpoint write but BEFORE pointer promotion.
  newcp=directory/"next.json"
  newcp.write_bytes(b'{"snapshotStatus":"PREPARING"}')
  tests["crash_before_pointer_keeps_LKG"]=(pointer.read_bytes()==a)
  # Simulated interrupted partial staging cannot replace last COMMITTED.
  (directory/"LATEST.stage").write_bytes(b'{"partial":')
  tests["interrupted_stage_keeps_LKG"]=(pointer.read_bytes()==a)
  (directory/"LATEST.stage").unlink()
  # Stale reader must not promote a conflicting new snapshot.
  pointer.write_bytes(b'{"other_writer":"committed"}')
  try:cas(pointer,a,b'{"us":"commit"}')
  except IntegrityError:tests["concurrent_CAS_rejects"]=(pointer.read_bytes()!=a)
  # Simulated intent-only effect remains UNKNOWN and cannot be replayed.
  opdir=directory/"OPERACIONES"
  opdir.mkdir()
  (opdir/"op1.intent.json").write_text('{"operationId":"op1"}',encoding="utf-8")
  pend,done=pending_intents(directory)
  tests["orphan_intent_detected_unknown"]=(len(pend)==1 and not done and pend[0]["status"]=="UNKNOWN_INTENT_WITHOUT_COMMIT")
  (opdir/"op1.commit.json").write_text('{"operationId":"op1","state":"SUCCEEDED_DOCUMENTARY_SCOPE"}',encoding="utf-8")
  pend,done=pending_intents(directory)
  tests["committed_intent_never_replays"]=(not pend and done==["op1"])
  # One altered byte must not match original SHA.
  original=b'{"id":"a","snapshotStatus":"COMMITTED"}'
  altered=b'{"id":"a","snapshotStatus":"C0MMITTED"}'
  tests["tamper_detected_by_sha"]=(sha(original)!=sha(altered))
 if not all(tests.values()):
  raise IntegrityError("RECOVERY_SIMULATION_FAILED:"+str(tests))
 return {"tests":tests,"passed":sum(tests.values()),"total":len(tests),
         "scope":"SYNTHETIC_LOCAL_CRASH_CAS_AND_INTENT_NOT_CROSS_CHAT_E2E"}

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--project-id",default="TCSA-CORE")
 p.add_argument("--self-test",action="store_true")
 args=p.parse_args()
 result=simulate() if args.self_test else retrieve(args.project_id)
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
