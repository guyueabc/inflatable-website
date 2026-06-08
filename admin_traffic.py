"""admin_traffic.py — 管理后台流量统计模块"""
import os, sqlite3, csv, io
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session, Response

import config

traffic_bp = Blueprint("admin_traffic", __name__, url_prefix="/api/admin/traffic")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"ok": False, "error": "未授权"}), 401
        return f(*args, **kwargs)
    return decorated

_date_column_ensured = False

def _ensure_date_column():
    global _date_column_ensured
    if _date_column_ensured:
        return
    try:
        with get_db() as conn:
            try:
                conn.execute("SELECT date FROM traffic LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE traffic ADD COLUMN date TEXT DEFAULT ''")
        _date_column_ensured = True
    except sqlite3.OperationalError:
        # Table doesn't exist yet — will be created by init_db() in app.py
        pass

def _pv_uv_for_range(start_date, end_date, where_extra="", params=None):
    if params is None: params = []
    where = "date>=? AND date<=?"
    if where_extra: where += f" AND {where_extra}"
    with get_db() as conn:
        pv = conn.execute(f"SELECT COUNT(*) AS cnt FROM traffic WHERE {where}", [start_date,end_date]+params).fetchone()["cnt"]
        uv = conn.execute(f"SELECT COUNT(DISTINCT ip) AS cnt FROM traffic WHERE {where}", [start_date,end_date]+params).fetchone()["cnt"]
    return pv, uv

def _daily_pv_for_range(start_date, end_date):
    rows = []
    with get_db() as conn:
        results = conn.execute("SELECT date,COUNT(*) AS pv,COUNT(DISTINCT ip) AS uv FROM traffic WHERE date>=? AND date<=? GROUP BY date ORDER BY date", (start_date,end_date)).fetchall()
        result_map = {r["date"]: {"pv":r["pv"],"uv":r["uv"]} for r in results}
    cur = datetime.strptime(start_date,"%Y-%m-%d").date()
    end = datetime.strptime(end_date,"%Y-%m-%d").date()
    while cur <= end:
        ds = cur.strftime("%Y-%m-%d")
        data = result_map.get(ds, {"pv":0,"uv":0})
        rows.append({"date":ds,"pv":data["pv"],"uv":data["uv"]})
        cur += timedelta(days=1)
    return rows

def _monthly_pv_for_range(start_date, end_date):
    with get_db() as conn:
        rows = conn.execute("SELECT substr(date,1,7) AS ym,COUNT(*) AS pv,COUNT(DISTINCT ip) AS uv FROM traffic WHERE date>=? AND date<=? GROUP BY ym ORDER BY ym", (start_date,end_date)).fetchall()
    return [dict(r) for r in rows]

def _page_distribution(start_date, end_date):
    page_names = {"/":"首页","/login":"登录页","/generate":"生成页","/messages":"聊天页","/verify":"验证页","/result":"结果页","/admin":"管理后台","/admin_login":"管理登录","/api":"API接口"}
    with get_db() as conn:
        rows = conn.execute("SELECT page,COUNT(*) AS cnt FROM traffic WHERE date>=? AND date<=? GROUP BY page ORDER BY cnt DESC LIMIT 15", (start_date,end_date)).fetchall()
    result = []
    for r in rows:
        page = r["page"]
        name = page
        for prefix, cn in page_names.items():
            if page == prefix or page.startswith(prefix):
                name = cn; break
        result.append({"page":name,"path":page,"count":r["cnt"]})
    return result

def _calc_growth(current, previous):
    if previous == 0: return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)

# ═══ Main summary endpoint ═══
@traffic_bp.route("/summary")
@admin_required
def api_traffic_summary():
    _ensure_date_column()
    period = request.args.get("period", "week")
    ref_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    ref = datetime.strptime(ref_str, "%Y-%m-%d").date()
    today_str = ref.strftime("%Y-%m-%d")

    if period == "day":
        yesterday = ref - timedelta(days=1)
        last_week = ref - timedelta(days=7)
        pv, uv = _pv_uv_for_range(today_str, today_str)
        pv_yest, uv_yest = _pv_uv_for_range(yesterday.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d"))
        pv_lw, uv_lw = _pv_uv_for_range(last_week.strftime("%Y-%m-%d"), last_week.strftime("%Y-%m-%d"))
        daily = _daily_pv_for_range((ref - timedelta(days=6)).strftime("%Y-%m-%d"), today_str)
        return jsonify({"ok":True,"period":"day","date":today_str,"pv":pv,"uv":uv,"pv_yesterday":pv_yest,"uv_yesterday":uv_yest,"pv_week_ago":pv_lw,"uv_week_ago":uv_lw,"pv_dod":_calc_growth(pv,pv_yest),"uv_dod":_calc_growth(uv,uv_yest),"daily":daily,"page_distribution":_page_distribution(today_str,today_str),"total_all":_pv_uv_for_range("2000-01-01","2099-12-31")[0]})

    elif period == "week":
        monday = ref - timedelta(days=ref.weekday())
        week_start = monday.strftime("%Y-%m-%d")
        week_end = today_str
        last_monday = monday - timedelta(days=7)
        last_sunday = monday - timedelta(days=1)
        pv, uv = _pv_uv_for_range(week_start, week_end)
        pv_last, uv_last = _pv_uv_for_range(last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d"))
        daily = _daily_pv_for_range(week_start, week_end)
        return jsonify({"ok":True,"period":"week","date_range":f"{week_start} ~ {week_end}","pv":pv,"uv":uv,"pv_last_week":pv_last,"uv_last_week":uv_last,"pv_wow":_calc_growth(pv,pv_last),"uv_wow":_calc_growth(uv,uv_last),"daily":daily,"page_distribution":_page_distribution(week_start,week_end),"total_all":_pv_uv_for_range("2000-01-01","2099-12-31")[0]})

    elif period == "month":
        month_start = ref.replace(day=1).strftime("%Y-%m-%d")
        month_end = today_str
        last_month = ref.replace(day=1) - timedelta(days=1)
        last_month_start = last_month.replace(day=1).strftime("%Y-%m-%d")
        last_month_end = last_month.strftime("%Y-%m-%d")
        pv, uv = _pv_uv_for_range(month_start, month_end)
        pv_last, uv_last = _pv_uv_for_range(last_month_start, last_month_end)
        daily = _daily_pv_for_range(month_start, month_end)
        return jsonify({"ok":True,"period":"month","date_range":f"{month_start} ~ {month_end}","pv":pv,"uv":uv,"pv_last_month":pv_last,"uv_last_month":uv_last,"pv_mom":_calc_growth(pv,pv_last),"uv_mom":_calc_growth(uv,uv_last),"daily":daily,"page_distribution":_page_distribution(month_start,month_end),"total_all":_pv_uv_for_range("2000-01-01","2099-12-31")[0]})

    elif period == "year":
        year_start = ref.replace(month=1,day=1).strftime("%Y-%m-%d")
        year_end = today_str
        last_year_start = ref.replace(year=ref.year-1,month=1,day=1).strftime("%Y-%m-%d")
        last_year_end = ref.replace(year=ref.year-1,month=12,day=31).strftime("%Y-%m-%d")
        pv, uv = _pv_uv_for_range(year_start, year_end)
        pv_last, uv_last = _pv_uv_for_range(last_year_start, last_year_end)
        monthly = _monthly_pv_for_range(year_start, year_end)
        return jsonify({"ok":True,"period":"year","date_range":f"{year_start} ~ {year_end}","pv":pv,"uv":uv,"pv_last_year":pv_last,"uv_last_year":uv_last,"pv_yoy":_calc_growth(pv,pv_last),"uv_yoy":_calc_growth(uv,uv_last),"monthly":monthly,"page_distribution":_page_distribution(year_start,year_end),"total_all":_pv_uv_for_range("2000-01-01","2099-12-31")[0]})

    return jsonify({"ok":False,"error":"无效的时间范围"}), 400

@traffic_bp.route("/logs")
@admin_required
def api_traffic_logs():
    limit = min(int(request.args.get("limit",50)), 200)
    with get_db() as conn:
        rows = conn.execute("SELECT page,ip,user_agent,date,created_at,country,referrer FROM traffic ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return jsonify({"ok":True,"logs":[dict(r) for r in rows]})

@traffic_bp.route("/page")
@admin_required
def api_traffic_page():
    today = datetime.now().strftime("%Y-%m-%d")
    total = _pv_uv_for_range("2000-01-01","2099-12-31")[0]
    today_pv, today_uv = _pv_uv_for_range(today, today)
    last_7 = _daily_pv_for_range((datetime.now()-timedelta(days=6)).strftime("%Y-%m-%d"), today)
    page_dist = _page_distribution("2000-01-01","2099-12-31")
    return jsonify({"ok":True,"total":total,"today":today_pv,"today_uv":today_uv,"last_7_days":last_7,"page_distribution":page_dist})

@traffic_bp.route("/export", endpoint="traffic_export_csv")
@admin_required
def api_traffic_export_csv():
    period = request.args.get("period", "week")
    today = datetime.now().date()

    if period == "day": start_date = today - timedelta(days=6)
    elif period == "week": start_date = today - timedelta(days=today.weekday())
    elif period == "month": start_date = today.replace(day=1)
    elif period == "year": start_date = today.replace(month=1,day=1)
    else: start_date = today - timedelta(days=6)
    end_date = today

    daily = _daily_pv_for_range(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
    total_all = _pv_uv_for_range("2000-01-01","2099-12-31")[0]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date","PV","UV","Period"])
    for d in daily:
        writer.writerow([d["date"],d["pv"],d["uv"],period])
    writer.writerow([])
    writer.writerow(["Total All PV",total_all])
    writer.writerow(["Date Range",str(start_date),str(end_date)])

    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":f"attachment;filename=traffic_{period}_{today}.csv"})
