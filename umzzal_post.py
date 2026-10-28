#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
아이돌 움짤 자동 게시 (kgirls.net → 누드티비 유머게시판, 2026-10-18 제프)
- 원본: kgirls 마이너갤·볼거리(새 글 많음) → kkzz.kr 움짤 공작소 → kgirls 그냥 움짤·입덕짤·그냥 은꼴(지난 글 재고)
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
KKZZ = "https://kkzz.kr"
ISSUYA = "https://www.issuya.com"
# 앞에서부터 우선 (kkzz = kkzz.kr 움짤 공작소, issuya = 이슈야 연예 갤러리)
SOURCES = ["issuya", "kkzz", "mgall", "issue", "kgif", "stars", "ggor"]   # 2026-10-22: kgirls 영상 차단으로 이슈야·kkzz 먼저
MAX_PAGE = 15
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 노출을 노린 표현만 건너뜀 (옷차림·스타일 단어는 통과, 2026-10-18 제프: 느슨하게)
# 엉덩이·골반·가슴·겨드랑이·내전근 같은 일상 부위 이름은 통과 (2026-10-19 제프: 한국어는 다 '엉덩이'라 함)
# 노출·젖·출렁·쩍벌·빼꼼·ㅗㅜㅑ도 통과 (2026-10-19 제프: 필터가 많으면 올릴 글이 없음)
BAD_WORDS = ["슴골", "언더붑", "엉밑", "팬티", "브라", "속옷", "Y존", "y존", "업스커트"]   # 업스커트: 2026-10-22 추가(1361번)
# 미성년(2008년 이후 출생) 멤버가 있는 그룹·멤버, 촬영 당시 미성년이었을 수 있는 멤버 → 건너뜀
MINOR = ["키키", "KiiiKiii", "아일릿", "ILLIT", "베이비몬스터", "베몬", "BABYMONSTER", "하츠투하츠", "Hearts2Hearts",
         "이즈나", "izna", "트리플에스", "tripleS", "미야오", "MEOVV", "유니스", "UNIS", "영파씨", "YOUNG POSSE",
         "이서", "혜인", "키비츠", "앳하트", "AtHeart", "오드유스", "ODD YOUTH"]
# 성인 멤버만 있는 그룹·멤버 (제목에 하나는 있어야 올림)
ADULT = ["블랙핑크", "로제", "지수", "제니", "리사", "트와이스", "나연", "정연", "모모", "사나", "지효", "미나", "다현",
         "채영", "쯔위", "레드벨벳", "아이린", "슬기", "웬디", "조이", "예리", "아이브", "안유진", "장원영", "리즈",
         "에스파", "카리나", "윈터", "지젤", "닝닝", "르세라핌", "사쿠라", "김채원", "허윤진", "카즈하", "은채",
         "민지", "하니", "다니엘", "해린", "있지", "예지", "리아", "류진", "채령", "엔믹스", "해원", "릴리", "설윤",
         "규진", "아이들", "미연", "민니", "소연", "우기", "슈화", "오마이걸", "효정", "유아", "승희", "유빈", "아린",
         "프로미스나인", "백지헌", "이채영", "이나경", "송하영", "박지원", "노지선", "케플러", "다연", "김채현",
         "최유진", "샤오팅", "히카루", "빌리", "츠키", "시윤", "문수아", "키스오브라이프", "키오프", "쥴리", "나띠",
         "스테이씨", "세은", "아이사", "재이", "우주소녀", "권은비", "전소미", "청하", "아이유", "태연", "윤아",
         "소녀시대", "마마무", "화사", "솔라", "문별", "휘인", "에이핑크", "비비", "이주은", "안지현", "설현", "AOA", "윤보미", "하이키", "브브걸", "브레이브걸스",
         # 성인 확인된 이름 추가 (2026-10-18)
         "라잇썸", "히나", "김민주", "남규리", "이세희", "김소현", "이나경", "아이칠린", "이다혜", "김한나",
         "수지", "한소희", "김유정", "고윤정", "김지원", "신세경", "박보영", "선미", "현아", "효린", "씨스타",
         "티아라", "에일리", "EXID", "솔지", "혜린", "걸스데이", "혜리", "설리", "크리스탈", "드림캐쳐",
         "위키미키", "최유정", "김도연", "이달의소녀", "츄", "희진", "하슬", "로켓펀치", "체리블렛"]


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
    t = title.replace("키스오브라이프", "키오프")   # '오브라이프' 속 '브라'가 걸리지 않게
    t = t.replace("브라톱", "톱")   # 브라톱은 옷차림이라 통과
    for w in BAD_WORDS:
        if w in t:
            return f"신체 부위 단어 '{w}'"
    for w in MINOR:
        # '이서'는 '가까이서'처럼 다른 말 속에 들어가므로 따로 쓰였을 때만
        hit = re.search(r"(^|[\s\[(])이서($|[\s\])])", t) if w == "이서" else (w in t)
        if hit:
            return f"미성년 멤버 가능 '{w}'"
    if not any(w in title for w in ADULT):
        return "누군지 확실하지 않음"
    return None


def list_page(board, page):
    """목록 한 쪽의 [(글 번호, 목록 제목 또는 None)] (최신순)"""
    if board == "kkzz":
        s = get(f"{KKZZ}/?mode=list&board_page={page}")
        out = {}
        for no, t in re.findall(r'href="https://kkzz\.kr/\?vid=(\d+)"[^>]*>(.*?)</a>', s, re.S):
            t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
            if t:
                out[int(no)] = t
        return sorted(out.items(), reverse=True)
    if board == "issuya":
        s = get(f"{ISSUYA}/bbs/board.php?bo_table=gallery&page={page}")
        out = {}
        for no, t in re.findall(r'bo_table=gallery&(?:amp;)?wr_id=(\d+)[^"]*"[^>]*>(.*?)</a>', s, re.S):
            t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()
            if t and int(no) not in out:
                out[int(no)] = t
        return sorted(out.items(), reverse=True)
    s = get(f"{SITE}/{board}?page={page}")
    return [(n, None) for n in sorted({int(n) for n in re.findall(rf'/{board}/(\d+)["?#]', s)}, reverse=True)]


def div_block(s, marker):
    """marker가 들어 있는 <div>부터 그 div가 닫히는 곳까지 (본문 칸만 잘라내기). 못 찾으면 빈 문자열"""
    a = s.find(marker)
    if a < 0:
        return ""
    i = s.rfind("<div", 0, a)
    depth = 0
    for m in re.finditer(r"<div\b|</div>", s[i:]):
        depth += 1 if m.group(0).startswith("<div") else -1
        if depth == 0:
            return s[i:i + m.end()]
    return s[i:]


def read_post(board, no, title=None):
    if board == "kkzz":
        s = get(f"{KKZZ}/?vid={no}")
        base = KKZZ
        img_pat = r'[^"]*wp-content/uploads/[^"]+'
    elif board == "issuya":
        page = get(f"{ISSUYA}/bbs/board.php?bo_table=gallery&wr_id={no}")
        # 본문 칸(view-content)만 봄 — 페이지 아래 '최근 갤러리' 칸의 다른 글 사진이 섞이지 않게 (2026-10-22 제프: 1443·1445번 중복 사진)
        s = div_block(page, 'class="view-content')
        # 본문 사진은 줄인 파일(thumb-…_1000x…)로 보이고 원본 주소는 content 속성에 있음 → 원본으로 바꿔 읽음
        s = re.sub(r'<img([^>]*?)\scontent="([^"]+)"([^>]*?)\ssrc="[^"]+"', r'<img\1\3 src="\2"', s)
        base = ISSUYA
        img_pat = r'[^"]*/data/(?:file/gallery|editor)/[^"]+'
    else:
        s = get(f"{SITE}/{board}/{no}")
        m = re.search(r"<title>([^<]*)</title>", s)
        title = html.unescape(m.group(1)).split(" - ")[0].strip() if m else ""
        base = SITE
        img_pat = r'[^"]*/files/attach/images/\d+/\d+/\d+/[^"]+\.(?:gif|jpe?g|png|webp)'
    media = []
    for m in re.finditer(rf'<(?:video|source)[^>]*?\ssrc=["\']([^"\']+\.mp4[^"\']*)["\']|<img[^>]*?\ssrc="({img_pat})"', s):
        u = html.unescape(m.group(1) or m.group(2))
        if u.startswith("//"):          # https: 가 빠진 주소 (2026-10-23, 1533·1534번 재생 안 됨)
            u = "https:" + u
        elif u.startswith("/"):
            u = base + re.sub(r"^/\./", "/", u)
        if "heye.kr/" in u:             # heye 서버 파일은 외부 링크 차단 → 안 씀
            continue
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
                rows = list_page(board, page)
            except Exception as e:
                print(f"  [목록 실패] {board} {page}쪽: {e}")
                break
            if not rows:
                break
            for no, list_title in rows:
                key = f"{board}/{no}"
                if key in rec["posted"] or key in rec["skipped"]:
                    continue
                if list_title and judge(list_title):   # 목록 제목으로 먼저 거르면 글을 안 열어도 됨
                    rec["skipped"][key] = {"title": list_title, "why": judge(list_title)}
                    save(POSTED, rec)
                    continue
                try:
                    title, media = read_post(board, no, list_title)
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


UPLOAD_BASE = "https://nudetv-v2-admin-backend.onrender.com"


def localize(media, h):
    """사진(jpg·png·webp)은 받아서 누드티비에 업로드한 주소로 바꿈 — 원본 사이트가 외부 사진 표시를 막아 엑박이 나서
    (2026-10-22 제프: 츠키-나띠 1433번 엑박). 움짤 mp4·GIF는 업로드하면 멈추므로 원본 주소 그대로. 업로드 실패한 사진은 뺌"""
    out = []
    for kind, u in media:
        path = u.split("?")[0].lower()
        if kind == "video" and "://www.kgirls.net/" in u:
            # www.kgirls.net 영상은 다른 사이트에서 링크하면 막힘(캐시돼 있을 때만 보임) → 넣지 않음 (2026-10-22, 1439번)
            print(f"    [영상 뺌] kgirls 링크 차단: {u[-40:]}")
            continue
        if kind == "video":
            # 올리기 전에 영상 파일이 실제로 열리는지 확인 (2026-10-24 제프: 1607번 — 원본에서 지워진 파일이 그대로 올라감)
            try:
                r = requests.get(u, headers={"User-Agent": UA, "Range": "bytes=0-1023"}, timeout=30, stream=True)
                alive = r.status_code in (200, 206) and r.headers.get("Content-Type", "").startswith("video/")
                r.close()
            except Exception:
                alive = False
            if not alive:
                print(f"    [영상 뺌] 열리지 않음: {u[-50:]}")
                continue
            out.append((kind, u))
            continue
        if path.endswith(".gif"):
            out.append((kind, u))
            continue
        try:
            img = requests.get(u, headers={"User-Agent": UA}, timeout=60)
            ctype = img.headers.get("Content-Type", "")
            if img.status_code != 200 or not ctype.startswith("image/"):
                raise RuntimeError(f"받기 실패 {img.status_code} {ctype}")
            name = os.path.basename(path) or "image.jpg"
            url, code = None, None
            for wait in (0, 10, 30):   # 누드티비 서버가 잠깐 502를 낼 때가 있어 3번까지 다시 시도
                time.sleep(wait)
                r = requests.post(f"{API}/upload", files={"image": (name, img.content, ctype)}, headers=h, timeout=120)
                code = r.status_code
                if code == 200:
                    url = (r.json() or {}).get("imageUrl")
                    break
            if not url:
                raise RuntimeError(f"업로드 실패 {code}")
            out.append(("img", url if url.startswith("http") else UPLOAD_BASE + url))
        except Exception as e:
            print(f"    [사진 뺌] {u[-50:]}: {e}")
    return out


def post_items(items, h, existing):
    """후보 목록을 올림. (올린 개수, 등록 실패가 있었는지)를 돌려줌"""
    rec = load(POSTED, {"posted": {}, "skipped": {}})   # candidates()가 기록한 건너뜀을 포함해 다시 읽음
    count, failed = 0, False
    for key, title, media in items:
        if title in existing:
            rec["skipped"][key] = {"title": title, "why": "게시판에 같은 제목 있음"}
            save(POSTED, rec)
            continue
        # 다른 글에 이미 쓴 원본 사진·영상은 뺌 (사이트 구조를 잘못 읽어 같은 사진이 여러 글에 붙는 것 방지, 2026-10-22)
        used = {x for p in rec["posted"].values() for x in p.get("urls", [])}
        media = [(k, x) for k, x in media if x not in used]
        src_urls = [x for _, x in media]
        media = localize(media, h)
        if not media:
            rec["skipped"][key] = {"title": title, "why": "움짤·사진 없음"}
            save(POSTED, rec)
            print(f"  [건너뜀] {title}: 쓸 수 있는 움짤·사진 없음")
            continue
        nick = pick_nick(rec)
        body = {"board_type": BOARD, "title": title, "content": to_html(media), "author_nickname": nick,
                "author_level": 99, "is_notice": False, "is_pinned": False, "is_published": True}
        r = requests.post(f"{API}/posts", json=body, headers=h, timeout=90)
        if r.status_code not in (200, 201):
            print(f"  [등록 실패] {title}: {r.status_code} {r.text[:200]}")
            failed = True
            continue
        d = r.json()
        pid = (d.get("post") or d.get("data") or d).get("id")
        rec["posted"][key] = {"id": pid, "title": title, "nick": nick, "media": len(media),
                              "at": now().strftime("%Y-%m-%d %H:%M"), "urls": src_urls}
        save(POSTED, rec)
        count += 1
        print(f"  [게시 완료] {pid} · {nick} · {title} (움짤·사진 {len(media)}개)")
        time.sleep(random.randint(20, 90))
    return count, failed


def submit(n):
    """n개를 올림. 후보가 건너뛰어지면(사진·영상 없음, 같은 제목 등) 다음 후보로 채움 (최대 6번, 2026-10-28 누락 방지)"""
    h = existing = None
    count = 0
    for _ in range(6):
        items = candidates(n - count)
        if not items:
            break
        if h is None:
            h = login()
            existing = public_titles()
        got, failed = post_items(items, h, existing)
        count += got
        if count >= n or failed:   # 등록이 실패한 실행은 같은 일을 반복하지 않고 다음 실행에 맡김
            break
    if h is None:
        print("[올릴 글 없음]")
    return count


def today_plan():
    """날마다 랜덤 개수(20~30)·24시간 랜덤 시각을 정해 schedule.json에 기록"""
    today = now().strftime("%Y-%m-%d")
    sch = load(SCHEDULE, {})
    if sch.get("date") != today:
        # 지난 날짜의 예정·올린 개수는 history에 남김 (매일 아침 점검 작업이 달력에 씀)
        hist = sch.get("history", {})
        if sch.get("date"):
            hist[sch["date"]] = {"target": len(sch.get("slots", [])), "carry": sch.get("carry", 0),
                                 "done": sch.get("done", 0)}
        hist = dict(sorted(hist.items())[-60:])
        # 어제 못 올린 개수는 오늘로 넘겨서 먼저 올림 (자정 넘어 서버가 늦게 깨어나도 누락 없게, 2026-10-20 제프)
        carry = max(0, len(sch.get("slots", [])) - sch.get("done", 0)) if sch.get("date") else 0
        n = random.randint(*PER_DAY)
        mins = sorted(random.sample(range(24 * 60), n))
        slots = [f"{m // 60:02d}:{m % 60:02d}" for m in mins]
        # 맨 처음 시작한 날만 이미 지난 시각을 건너뜀 (날짜가 바뀔 때는 건너뛰지 않음)
        first = not sch.get("date")
        done = sum(1 for t in slots if t < now().strftime("%H:%M")) if first else 0
        sch = {"date": today, "slots": slots, "done": done, "carry": carry, "history": hist}
        save(SCHEDULE, sch)
    return sch


def auto():
    sch = today_plan()
    due = sch.get("carry", 0) + sum(1 for t in sch["slots"] if t <= now().strftime("%H:%M"))
    need = min(due - sch["done"], MAX_PER_RUN)
    print(f"[{now():%Y-%m-%d %H:%M}] 오늘 {len(sch['slots'])}개 예정(+어제 넘어온 {sch.get('carry', 0)}) · 지금까지 예정 {due} · 올림 {sch['done']}")
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
