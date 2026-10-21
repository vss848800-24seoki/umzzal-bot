#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
안구정화(움짤) 자동 게시 점검용 요약 (예약 작업 umzzal-daily-report가 이 명령 하나만 실행, 2026-10-21)
- 저장소 최신 기록을 받고(git pull), 오늘·어제 목표·게시 개수, 서버 실행 상태를 JSON으로 출력
- 읽기만 함 (글 등록·삭제 없음, 원본 사이트 요청 없음, 비밀값 출력 없음)
실행: python3 ~/Downloads/움짤작업/report.py
"""
import collections, datetime, json, os, subprocess
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
GH = os.path.expanduser("~/.local/bin/gh")
REPO = "vss848800-24seoki/umzzal-bot"


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


subprocess.run(["git", "-C", HERE, "pull", "-q", "--rebase"], capture_output=True)
now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
T = now.strftime("%Y-%m-%d")
Y = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
hm = now.strftime("%H:%M")

posted = load("posted.json")
sch = load("schedule.json")
cnt = collections.Counter(v.get("at", "")[:10] for v in posted.get("posted", {}).values())
hist = sch.get("history", {})

today = {"date": T, "posted": cnt.get(T, 0)}
if sch.get("date") == T:
    slots = sch.get("slots", [])
    carry = sch.get("carry", 0)
    today.update(target=len(slots) + carry, carry=carry, done=sch.get("done", 0),
                 due_now=carry + sum(1 for t in slots if t <= hm),
                 left=[t for t in slots if t > hm])
yest = {"date": Y, "posted": cnt.get(Y, 0)}
if Y in hist:
    yest.update(target=(hist[Y].get("target") or 0) + hist[Y].get("carry", 0),
                carry=hist[Y].get("carry", 0), done=hist[Y].get("done"))
yest["carried_to_today"] = today.get("carry", 0)

runs = []
try:
    out = subprocess.run([GH, "run", "list", "--repo", REPO, "--workflow", "umzzal.yml", "-L", "30",
                          "--json", "databaseId,createdAt,conclusion,status"],
                         capture_output=True, text=True, timeout=60).stdout
    runs = json.loads(out or "[]")
except Exception as e:
    runs = [{"error": str(e)}]

last = runs[0] if runs and "createdAt" in runs[0] else {}
fails = [r for r in runs if r.get("conclusion") == "failure"]
fail_reason = ""
if fails:
    try:
        log = subprocess.run([GH, "run", "view", str(fails[0]["databaseId"]), "--repo", REPO, "--log"],
                             capture_output=True, text=True, timeout=90).stdout
        for line in log.splitlines():
            if any(k in line for k in ("[오류]", "로그인 실패", "등록 실패", "목록 실패", "올릴 글 없음")):
                fail_reason = line.split("Z ", 1)[-1][:200]
                break
    except Exception:
        pass

recent_skip = list(posted.get("skipped", {}).values())[-30:]
print(json.dumps({
    "now": now.strftime("%Y-%m-%d %H:%M"),
    "today": today,
    "yesterday": yest,
    "last_run_utc": last.get("createdAt"),
    "last_run_minutes_ago": round((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(
        last["createdAt"].replace("Z", "+00:00"))).total_seconds() / 60) if last else None,
    "failures_in_last_30": len(fails),
    "fail_reason": fail_reason,
    "recent_skip_no_media": sum(1 for v in recent_skip if v.get("why") == "움짤·사진 없음"),
}, ensure_ascii=False, indent=1))
