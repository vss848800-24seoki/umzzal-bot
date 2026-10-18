#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
아이돌 움짤 자동 게시 (kgirls.net → 누드티비 유머게시판, 2026-10-18 제프)
- 원본: kgirls 마이너갤·볼거리(새 글 많음) → 그냥 움짤·입덕짤·그냥 은꼴(지난 글 재고)
- 움짤(mp4)·사진은 원본 주소 그대로 링크 걸기(<video>/<img>). 누드티비 업로드는 GIF를 멈춘 사진으로 바꿔서 안 씀
- 어드민 API로 작성(로그인 영상특파원 구미호), 글쓴이는 nicknames.json 100개 중 랜덤
- 제목은 원글 제목 그대로
- 하루 20~30개(날마다 랜덤 개수), 24시간 랜덤 시각
- 걸러내기: 제목에 신체 부위를 집는 단어가 있으면 건너뜀 / 미성년 멤버가 있는 그룹·멤버면 건너뜀 /
           제목에 성인 멤버만 있는 그룹·멤버 이름이 없으면(누군지 확실하지 않으면) 건너뜀
- 같은 원글·같은 제목은 다시 안 올림 (posted.json)
- 토큰·비밀번호는 화면/로그에 절대 출력하지 않음

실행: python3 umzzal_post.py            (미리보기: 다음에 올릴 글 5개와 오늘 예정 시각)
      python3 umzzal_post.py --submit   (지금 바로 1개 등록)
      python3 umzzal_post.py --auto     (서버용: 예정 시각이 지난 만큼 등록, 한 번에 최대 4개)
"""
import datetime, html, json, os, random, re, sys, time
from zoneinfo import ZoneInfo
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
POSTED = os.path.join(HERE, "posted.json")
SCHEDULE = os.path.join(HERE, "schedule.json")
NICKS = os.path.join(HERE, "nicknames.json")

API = "https://nudetv-v2-admin-backend.onrender.com/api/admin"
PUBLIC = "https://nudetv-v2-backend.onrender.com/api/bulletin-board"
CRED = os.path.expanduser("~/.config/jeff/nudetv_admin")
ADMIN_NICK = "영상특파원 구미호"
BOARD = "humor"
PER_DAY = (20, 30)
MAX_PER_RUN = 4

SITE = "https://www.kgirls.net"
SOURCES = ["mgall", "issue", "kgif", "stars", "ggor"]   # 앞에서부터 우선
MAX_PAGE = 15
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 신체 부위를 집는 제목은 건너뜀
BAD_WORDS = ["가슴", "슴골", "언더붑", "엉밑", "엉벅지", "엉덩이", "골반", "팬티", "브라", "내전근", "겨드랑",
             "노출", "야벅지", "Y존", "y존", "젖", "속옷", "란제리", "ㅗㅜㅑ", "묵직", "출렁", "쩍벌", "비치는"]
# 미성년(2008년 이후 출생) 멤버가 있는 그룹·멤버, 촬영 당시 미성년이었을 수 있는 멤버 → 건너뜀
MINOR = ["키키", "KiiiKiii", "아일릿", "ILLIT", "베이비몬스터", "베몬", "BABYMONSTER", "하츠투하츠", "Hearts2Hearts",
         "이즈나", "izna", "트리플에스", "tripleS", "미야오", "MEOVV", "유니스", "UNIS", "영파씨", "YOUNG POSSE",
         "이서", "혜인", "키비츠"]
# 성인 멤버만 있는 그룹·멤버 (제목에 하나는 있어야 올림)
ADULT = ["블랙핑크", "로제", "지수", "제니", "리사", "트와이스", "나연", "정연", "모모", "사나", "지효", "미나", "다현",
         "채영", "쯔위", "레드벨벳", "아이린", "슬기", "웬디", "조이", "예리", "아이브", "안유진", "장원영", "리즈",
         "에스파", "카리나", "윈터", "지젤", "닝닝", "르세라핌", "사쿠라", "김채원", "허윤진", "카즈하", "은채",
         "민지", "하니", "다니엘", "해린", "있지", "예지", "리아", "류진", "채령", "엔믹스", "해원", "릴리", "설윤",
         "규진", "아이들", "미연", "민니", "소연", "우기", "슈화", "오마이걸", "효정", "유아", "승희", "유빈", "아린",
         "프로미스나인", "백지헌", "이채영", "이나경", "송하영", "박지원", "노지선", "케플러", "다연", "김채현",
         "최유진", "샤오팅", "히카루", "빌리", "츠키", "시윤", "문수아", "키스오브라이프", "키오프", "쥴리", "나띠",
         "스테이씨", "세은", "아이사", "재이", "우주소녀", "권은비", "전소미", "청하", "아이유", "태연", "윤아",
         "소녀시대", "마마무", "화사", "솔라", "문별", "휘인", "에이핑크", "비비", "이주은", "안지현", "설현", "AOA"]


def now():
    return datetime.datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, data):
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    return r.text


def judge(title):
    """올려도 되면 None, 아니면 건너뛰는 이유"""
    for w in BAD_WORDS:
        if w in title:
            return f"신체 부위 단어 '{w}'"
    for w in MINOR:
        if w in title:
            return f"미성년 멤버 가능 '{w}'"
    if not any(w in title for w in ADULT):
        return "누군지 확실하지 않음"
    return None


def read_post(board, no):
    s = get(f"{SITE}/{board}/{no}")
    m = re.search(r"<title>([^<]*)</title>", s)
    title = html.unescape(m.group(1)).split(" - ")[0].strip() if m else ""
    media = []
    for m in re.finditer(r'<video[^>]*?\ssrc="([^"]+)"|<img[^>]*?\ssrc="([^"]*/files/attach/images/\d+/\d+/\d+/[^"]+\.(?:gif|jpe?g|png|webp))"', s):
        u = html.unescape(m.group(1) or m.group(2))
        if u.startswith("/"):
            u = SITE + re.sub(r"^/\./", "/", u)
        kind = "video" if m.group(1) else "img"
        if (kind, u) not in media:
            media.append((kind, u))
    return title, media


def to_html(media):
    out = []
    for kind, u in media:
        u = html.escape(u, quote=True)
        if kind == "video":
            out.append(f'<p><video src="{u}" autoplay muted loop playsinline controls style="max-width:100%"></video></p>')
        else:
            out.append(f'<p><img src="{u}" style="max-width:100%"></p>')
    return "\n".join(out)


def candidates(need):
    """아직 안 올린 글을 우선순위대로 need개까지 찾음"""
    rec = load(POSTED, {"posted": {}, "skipped": {}})
    done_titles = {v["title"] for v in rec["posted"].values()}
    found = []
    for board in SOURCES:
        for page in range(1, MAX_PAGE + 1):
            try:
                s = get(f"{SITE}/{board}?page={page}")
            except Exception as e:
                print(f"  [목록 실패] {board} {page}쪽: {e}")
                break
            nos = sorted({int(n) for n in re.findall(rf'/{board}/(\d+)["?#]', s)}, reverse=True)
            if not nos:
                break
            for no in nos:
                key = f"{board}/{no}"
                if key in rec["posted"] or key in rec["skipped"]:
                    continue
                try:
                    title, media = read_post(board, no)
                except Exception as e:
                    print(f"  [글 읽기 실패] {key}: {e}")
                    continue
                why = judge(title) or (None if media else "움짤·사진 없음") or ("이미 올린 제목" if title in done_titles else None)
                if why:
                    rec["skipped"][key] = {"title": title, "why": why}
                    save(POSTED, rec)
                    continue
                found.append((key, title, media))
                if len(found) >= need:
                    return found
                time.sleep(1)
    return found


def login():
    if os.environ.get("NUDETV_ADMIN_ID") and os.environ.get("NUDETV_ADMIN_PW"):
        uid, pw = os.environ["NUDETV_ADMIN_ID"], os.environ["NUDETV_ADMIN_PW"]
    else:
        uid, pw = [l.strip() for l in open(CRED, encoding="utf-8").read().splitlines()[:2]]
    r = requests.post(f"{API}/auth/login", json={"login_id": uid, "password": pw}, timeout=90)
    if r.status_code != 200:
        raise RuntimeError(f"로그인 실패 {r.status_code}")
    d = r.json()
    token = d.get("token") or d.get("accessToken") or (d.get("data") or {}).get("token")
    h = {"Authorization": f"Bearer {token}"}
    me = requests.get(f"{API}/auth/me", headers=h, timeout=30).json()
    nick = (me.get("user") or me.get("admin") or me or {}).get("nickname")
    if nick != ADMIN_NICK:
        raise RuntimeError(f"[계정 불일치] 기대 '{ADMIN_NICK}' / 로그인 '{nick}' → 등록 안 함")
    return h


def public_titles():
    try:
        r = requests.get(PUBLIC, params={"board": BOARD, "page": 1, "limit": 50}, timeout=60)
        return {p.get("title", "").strip() for p in (r.json().get("posts") or [])}
    except Exception:
        return set()


def pick_nick(rec):
    nicks = load(NICKS, [])
    recent = [v.get("nick") for v in sorted(rec["posted"].values(), key=lambda v: v.get("at", ""))[-15:]]
    pool = [n for n in nicks if n not in recent] or nicks
    return random.choice(pool)


def submit(n):
    items = candidates(n)
    if not items:
        print("[올릴 글 없음]")
        return 0
    h = login()
    existing = public_titles()
    rec = load(POSTED, {"posted": {}, "skipped": {}})
    count = 0
    for key, title, media in items:
        if title in existing:
            rec["skipped"][key] = {"title": title, "why": "게시판에 같은 제목 있음"}
            save(POSTED, rec)
            continue
        nick = pick_nick(rec)
        body = {"board_type": BOARD, "title": title, "content": to_html(media), "author_nickname": nick,
                "author_level": 99, "is_notice": False, "is_pinned": False, "is_published": True}
        r = requests.post(f"{API}/posts", json=body, headers=h, timeout=90)
        if r.status_code not in (200, 201):
            print(f"  [등록 실패] {title}: {r.status_code} {r.text[:200]}")
            continue
        d = r.json()
        pid = (d.get("post") or d.get("data") or d).get("id")
        rec["posted"][key] = {"id": pid, "title": title, "nick": nick, "media": len(media),
                              "at": now().strftime("%Y-%m-%d %H:%M")}
        save(POSTED, rec)
        count += 1
        print(f"  [게시 완료] {pid} · {nick} · {title} (움짤·사진 {len(media)}개)")
        time.sleep(random.randint(20, 90))
    return count


def today_plan():
    """날마다 랜덤 개수(20~30)·24시간 랜덤 시각을 정해 schedule.json에 기록"""
    today = now().strftime("%Y-%m-%d")
    sch = load(SCHEDULE, {})
    if sch.get("date") != today:
        n = random.randint(*PER_DAY)
        mins = sorted(random.sample(range(24 * 60), n))
        slots = [f"{m // 60:02d}:{m % 60:02d}" for m in mins]
        # 하루 중간에 처음 만들면 이미 지난 시각은 건너뜀 (한꺼번에 몰려 올라가지 않게)
        sch = {"date": today, "slots": slots, "done": sum(1 for t in slots if t < now().strftime("%H:%M"))}
        save(SCHEDULE, sch)
    return sch


def auto():
    sch = today_plan()
    due = sum(1 for t in sch["slots"] if t <= now().strftime("%H:%M"))
    need = min(due - sch["done"], MAX_PER_RUN)
    print(f"[{now():%Y-%m-%d %H:%M}] 오늘 {len(sch['slots'])}개 예정 · 지금까지 예정 {due} · 올림 {sch['done']}")
    if need <= 0:
        return
    got = submit(need)
    sch["done"] += got
    save(SCHEDULE, sch)


def preview():
    sch = today_plan()
    print(f"오늘 {len(sch['slots'])}개 예정: {' '.join(sch['slots'])} (올림 {sch['done']})")
    for key, title, media in candidates(5):
        print(f"  {key}  {title}  (움짤·사진 {len(media)}개)")
    rec = load(POSTED, {"posted": {}, "skipped": {}})
    print(f"건너뛴 글 {len(rec['skipped'])}개 (이유는 posted.json)")


if __name__ == "__main__":
    try:
        if "--auto" in sys.argv:
            auto()
        elif "--submit" in sys.argv:
            submit(1)
        else:
            preview()
    except Exception as e:
        print(f"[오류] {e}")
        sys.exit(1)
