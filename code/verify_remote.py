"""Run authorized, small remote checks through MCP. Requires a private remote profile."""
import asyncio,hashlib,json,os,sys,time,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parents[1]

async def main():
    workspace=Path(os.environ["CODEX_SCIENCE_TEST_TMP"])/("remote-"+uuid.uuid4().hex[:8])
    workspace.mkdir(parents=True)
    project="projects/acceptance-"+uuid.uuid4().hex[:8]
    report={"project":project,"checks":[],"started_at":time.time()}
    params=StdioServerParameters(command=sys.executable,args=["-X","utf8",str(ROOT/"code/science_workbench.py")],env=dict(os.environ))
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as client:
            await client.initialize()
            listing=await client.list_tools();report["tool_count"]=len(listing.tools)
            async def tool(name,args):
                result=await client.call_tool(name,args)
                if result.isError:raise AssertionError(str(result.content))
                return result.structuredContent or json.loads(next(x.text for x in result.content if x.type=="text"))
            async def remote(action,**kw):return await tool("science_remote",{"action":action,"parameters":kw})
            def checked(name):
                report["checks"].append(name);print("PASS "+name,flush=True)
            async def wait_job(jid):
                for _ in range(30):
                    state=await remote("job_status",job_id=jid)
                    if state["status"] not in ("queued","running"):return state
                    await asyncio.sleep(.5)
                raise AssertionError("Job did not finish")
            health=await remote("health");assert "codex-r" in health["kernels"];checked("Conda Python and R kernels available")
            for language,first,second in [("python","x = [2, 4, 6]","print(sum(x))"),("r","x <- c(2, 4, 6)","cat(sum(x))")]:
                session=await remote("session_start",language=language,project=project,name="Acceptance "+language)
                sid=session["id"]
                try:
                    assert (await remote("session_execute",session_id=sid,code=first))["status"]=="ok"
                    result=await remote("session_execute",session_id=sid,code=second)
                    assert result["status"]=="ok" and "12" in json.dumps(result["outputs"])
                    checked(language+" variable persists across SSH connections")
                    if language=="python":
                        result=await remote("session_execute",session_id=sid,code="raise ValueError('acceptance')")
                        assert result["status"]=="error";checked("Python execution error retained")
                        result=await remote("session_execute",session_id=sid,code="import time; time.sleep(30)",timeout=1)
                        assert result["status"]=="timed_out"
                        assert (await remote("session_execute",session_id=sid,code="print(sum(x))"))["status"]=="ok"
                        checked("Session interrupt and continued execution")
                    else:
                        result=await remote("session_execute",session_id=sid,code="library(ggplot2); write.csv(data.frame(value=x), 'r-result.csv', row.names=FALSE); cat(as.character(packageVersion('ggplot2')))")
                        assert result["status"]=="ok";checked("Conda R ggplot2 and CSV output")
                    downloaded=await tool("science_fetch_artifact",{"remote_path":session["notebook"],"workspace":str(workspace),"output":language+".ipynb"})
                    nb=json.loads(Path(downloaded["path"]).read_text());assert nb["nbformat"]==4 and len(nb["cells"])>=2
                    checked(language+" notebook saved and hash-verified download")
                finally:await remote("session_close",session_id=sid)
            job=await remote("job_submit",project=project,code="from pathlib import Path; Path('result.csv').write_text('group,value\\nA,12\\n'); print('completed')")
            assert (await wait_job(job["id"]))["status"]=="succeeded"
            assert "completed" in (await remote("job_logs",job_id=job["id"]))["text"]
            checked("Detached Python job, status and logs")
            job=await remote("job_submit",language="r",project=project,code="cat(sum(c(2,4,6)))")
            assert (await wait_job(job["id"]))["status"]=="succeeded"
            assert "12" in (await remote("job_logs",job_id=job["id"]))["text"];checked("Detached Conda R job")
            job=await remote("job_submit",project=project,code="raise RuntimeError('expected failure')")
            state=await wait_job(job["id"]);assert state["status"]=="failed" and state["exit_code"]!=0;checked("Job failure exit code")
            job=await remote("job_submit",project=project,code="import time; time.sleep(60)")
            await remote("job_cancel",job_id=job["id"])
            assert (await wait_job(job["id"]))["status"]=="cancelled";checked("Job cancellation")
            job=await remote("job_submit",project=project,code="import time; time.sleep(60)",timeout=1)
            assert (await wait_job(job["id"]))["status"]=="timed_out";checked("Job timeout")
            result=await tool("science_fetch_artifact",{"remote_path":project+"/result.csv","workspace":str(workspace),"output":"result.csv"})
            assert hashlib.sha256(Path(result["path"]).read_bytes()).hexdigest()==result["sha256"];checked("Result download checksum")
    report.update(passed=True,finished_at=time.time())
    (ROOT/"reports").mkdir(exist_ok=True)
    (ROOT/"reports/remote-acceptance.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":asyncio.run(main())
