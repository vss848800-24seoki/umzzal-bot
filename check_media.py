#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이미 올린 안구정화 글의 kgirls 영상이 아직 재생되는지 점검 → 안 되면 고치거나 삭제 (2026-10-22 제프)
- www.kgirls.net 영상은 다른 사이트에서 링크하면 막힘(중간 서버에 저장돼 있을 때만 보임) → 저장이 만료되면 재생 안 됨
- 누드티비 글 화면에서 보는 것과 같은 조건(누드티비 글 주소가 출처)으로 영상 앞부분만 요청해서 확인
- 안 되는 영상만 있는 글 → 글 삭제 / 다른 미디어와 섞인 글 → 안 되는 영상만 빼고 수정
- 삭제·수정 전 글쓴이가 nicknames.json 닉네임인지 확인 (다른 사람 글은 절대 안 건드림)
- 기록: posted.json 의 그 글에 "removed"(삭제 시각·이유) 또는 "trimmed"(뺀 영상 수)
실행: python3 check_media.py          (미리보기: 목록만)
      python3 check_media.py --apply  (실제 삭제·수정)
"""
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor
import requests
import umzzal_post as u

PUBLIC = "https://nudetv-v2-backend.onrender.com/api/bulletin-board"
POST_URL = "https://nude-tv.net/community/humor/{}"


def video_ok(src, pid):
    """누드티비 글에서 볼 때처럼 요청 → 영상이 오면 True"""
    for _ in range(2):
        try:
            r = requests.get(src, headers={"User-Agent": u.UA, "Referer": POST_URL.format(pid), "Range": "bytes=0-1023"},
                             timeout=30, stream=True)
            ok = r.status_code in (200, 206) and r.headers.get("Content-Type", "").startswith("video/")
            r.close()
            if ok:
                return True
            if r.status_code in (403, 404, 410):
                return False
        except Exception:
            pass
        time.sleep(5)
    return False


def main(apply):
    rec = u.load(u.POSTED, {"posted": {}, "skipped": {}})
    nicks = set(u.load(u.NICKS, [])) | {"밤산책하는고양이"}
    h = u.login() if apply else None
    deleted = trimmed = checked = 0
    for key, v in list(rec["posted"].items()):
        if v.get("removed"):
            continue
        pid = v["id"]
        try:
            p = requests.get(f"{PUBLIC}/{pid}", timeout=60).json()
            p = p.get("post") or p.get("data") or p
        except Exception as e:
            print(f"  [읽기 실패] {pid}: {e}")
            continue
        content = p.get("content") or ""
        vids = re.findall(r'<video[^>]*src="([^"]+)"', content)
        bad = vids   # 2026-10-23: kgirls뿐 아니라 모든 영상 점검 (주소 버그·다른 사이트 차단도 잡게)
        if not bad:
            continue
        checked += 1
        # 영상 여러 개를 동시에 확인 (모든 영상 점검으로 늘어난 시간 줄이기, 2026-10-23)
        with ThreadPoolExecutor(max_workers=8) as ex:
            oks = list(ex.map(lambda s: video_ok(s, pid), bad))
        broken = [s for s, ok in zip(bad, oks) if not ok]
        if not broken:
            continue
        others = len(vids) - len(broken) + len(re.findall(r"<img", content))
        action = "삭제" if others == 0 else f"영상 {len(broken)}개 빼기"
        print(f"  [{action}] {pid} {v['title'][:25]} (안 됨 {len(broken)}/{len(vids)})")
        if not apply:
            continue
        if p.get("author_nickname") not in nicks:
            print(f"    [건너뜀] 글쓴이 '{p.get('author_nickname')}'가 우리 닉네임이 아님")
            continue
        if others == 0:
            r = requests.delete(f"{u.API}/posts/{pid}", headers=h, timeout=60)
            if r.status_code in (200, 204):
                v["removed"] = {"at": u.now().strftime("%Y-%m-%d %H:%M"), "why": "kgirls 영상 재생 안 됨"}
                deleted += 1
            else:
                print(f"    [삭제 실패] {r.status_code} {r.text[:120]}")
        else:
            a = requests.get(f"{u.API}/posts/{pid}", headers=h, timeout=60).json()
            a = a.get("post") or a.get("data") or a
            c = a["content"]
            for s in broken:
                c = re.sub(r'<p><video[^>]*src="' + re.escape(s) + r'"[^>]*></video></p>\n?', "", c)
            body = {k: a.get(k) for k in ("board_type", "title", "author_nickname", "author_level",
                                          "is_notice", "is_pinned", "is_published")}
            body["content"] = c
            r = requests.put(f"{u.API}/posts/{pid}", json=body, headers=h, timeout=90)
            if r.status_code in (200, 201):
                v["trimmed"] = v.get("trimmed", 0) + len(broken)
                trimmed += 1
            else:
                print(f"    [수정 실패] {r.status_code} {r.text[:120]}")
        u.save(u.POSTED, rec)
        time.sleep(2)
    print(f"[점검 끝] 영상 글 {checked}개 확인 · 삭제 {deleted} · 수정 {trimmed}" + ("" if apply else " (미리보기)"))


if __name__ == "__main__":
    try:
        main("--apply" in sys.argv)
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)
