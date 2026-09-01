"""SICAU jiaowu timetable scraping via the WebVPN (Playwright-driven).

Stateless per request: each call authenticates fresh through the public WebVPN
CAS (`auth.sicau.edu.cn`) and navigates the jiaowu DOM. No cookies persisted.

Use v1 (`sicau_timetable`) when the deployment can hit `jiaowu.sicau.edu.cn`
directly; v2 when the school has blocked off-campus / cloud access.
"""