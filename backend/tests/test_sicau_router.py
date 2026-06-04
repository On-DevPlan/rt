import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from rt_backend.core.config import Settings
from rt_backend.core.http import HttpClientHolder
from rt_backend.sicau_timetable.router import build_router

BASE = "https://jiaowu.sicau.edu.cn"


def _login_page_html() -> str:
    return """<html><body>
    <form name="form1">
        <input name="user"/>
        <input name="pwd"/>
        <input name="sign" value="SGN"/>
        <input name="hour_key" value="HRS"/>
    </form>
    </body></html>"""


def _timetable_html() -> str:
    return """<html><body><table>
    <tr><th>校区</th><th>课程名称</th><th>编号</th><th>周次</th><th>教室</th><th>上课时间</th><th>学分</th><th>学时</th><th>周学时</th><th>实验周学时</th><th>考核方法</th><th>教师</th><th>选课方式</th><th>混合式教学</th></tr>
    <tr><td>雅安</td><td>测试课</td><td>CS001</td><td>1-2</td><td>A101</td><td>1-1,1-2</td><td>2</td><td>32</td><td>2</td><td>0</td><td>考试</td><td>张老师</td><td>正常</td><td>否</td></tr>
    </table></body></html>"""


def _index1_html(user: str) -> str:
    return f"<html>欢迎 {user} 学生-课业信息</html>"


def _gbk_response(text: str, status_code: int = 200, headers: dict | None = None) -> Response:
    return Response(status_code, content=text.encode("gbk", errors="replace"), headers=headers)


@pytest.mark.asyncio
async def test_sicau_timetable_success():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    await holder.start()
    settings = Settings(sicau_default_semester="2025-2026-2")
    app.include_router(build_router(lambda: holder, settings))

    with respx.mock(base_url=BASE) as router:
        router.get("/web/web/web/index.asp").mock(
            return_value=_gbk_response(_login_page_html())
        )
        router.post("/jiaoshi/bangong/check.asp").mock(
            return_value=_gbk_response(
                _index1_html("202300000"),
                headers={"Location": "/index1.asp"},
            )
        )
        router.get("/xuesheng/gongxuan/gongxuan/xszhinan.asp").mock(
            return_value=_gbk_response("<html></html>")
        )
        router.get("/xuesheng/gongxuan/gongxuan/kbbanji.asp").mock(
            return_value=_gbk_response(_timetable_html())
        )

        with TestClient(app) as client:
            r = client.post(
                "/api/sicau/timetable",
                json={"user_id": "202300000", "password": "pw"},
            )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == "202300000"
    assert body["semester"] == "2025-2026-2"
    # slot 1,2 都映射到 period 1，去重后只剩一行
    assert "测试课 @ 1 1 w1,2 A101 张老师" in body["dsl"]
    assert body["course_count"] == 1


def test_sicau_timetable_missing_user_id():
    app = FastAPI()
    holder = HttpClientHolder(timeout=5.0)
    settings = Settings()
    app.include_router(build_router(lambda: holder, settings))
    with TestClient(app) as client:
        r = client.post("/api/sicau/timetable", json={"password": "pw"})
    assert r.status_code == 422
