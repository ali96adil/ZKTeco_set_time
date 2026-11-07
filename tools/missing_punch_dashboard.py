"""Loopback-only attendance review dashboard.

Reads local report/notes. Supports manual deletion of review notes only.
No access to the ZKTeco device and no clock-write commands.
"""
import argparse
import html
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from missing_punch_notes import MissingPunchNotes


def serve(report_path, notes_path, port):
    token = secrets.token_urlsafe(24)
    notes = MissingPunchNotes(notes_path)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, content_type="text/html; charset=utf-8"):
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/":
                return self.respond(404, "Not found", "text/plain; charset=utf-8")
            try:
                report = json.loads(Path(report_path).read_text(encoding="utf-8"))
                current = notes.load()
            except (OSError, ValueError) as exc:
                return self.respond(503, "Report unavailable: " + html.escape(str(exc)))
            employee = html.escape(str(report.get("employee_id", "")))
            rows = []
            for finding in report.get("findings", []):
                day = html.escape(str(finding.get("date", "")))
                status = html.escape(str(finding.get("status", "")))
                missing = ", ".join(map(str, finding.get("missing", []))) or "—"
                rows.append(f"<tr><td>{day}</td><td>{status}</td><td>{html.escape(missing)}</td></tr>")
            cards = []
            for key, note in sorted(current.items()):
                if str(note.get("employee_id")) != str(report.get("employee_id")):
                    continue
                day = html.escape(str(note.get("date", "")))
                kind = html.escape(str(note.get("kind", "")))
                cards.append(f'<article><b>{day}</b> — {kind}<form method="post" action="/delete"><input type="hidden" name="csrf" value="{token}"><input type="hidden" name="date" value="{day}"><input type="hidden" name="kind" value="{kind}"><button>حذف الملاحظة</button></form></article>')
            page = f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>مراجعة البصمات</title>
<style>body{{font:16px system-ui;background:#0c1725;color:#eef5ff;max-width:700px;margin:auto;padding:20px}}
article,section{{background:#17283c;padding:16px;margin:12px 0;border-radius:12px}}
table{{width:100%;border-collapse:collapse}}td,th{{border-bottom:1px solid #456;padding:10px;text-align:right}}
button{{padding:10px;border-radius:8px;cursor:pointer}}small{{color:#bcd}}</style></head><body>
<h1>مراجعة البصمات المفقودة</h1><p>الموظف {employee} — آخر أربعة أيام مكتملة</p>
<section><h2>نتائج آخر فحص</h2><table><tr><th>التاريخ</th><th>الحالة</th><th>الملاحظة</th></tr>{''.join(rows)}</table></section>
<section><h2>الملاحظات المحفوظة</h2>{''.join(cards) or '<p>لا توجد ملاحظات محفوظة</p>'}
<form method="post" action="/delete-all"><input type="hidden" name="csrf" value="{token}"><button>حذف كل ملاحظات هذا الموظف</button></form>
<form method="post" action="/delete-old"><input type="hidden" name="csrf" value="{token}"><button>حذف الملاحظات الأقدم من 7 أيام</button></form></section>
<small>الحذف لا يغير سجلات الجهاز. الفحص الجديد يتم من برنامج الاستيراد ويعيد الملاحظة إذا استمر النقص.</small>
</body></html>"""
            self.respond(200, page)

        def do_POST(self):
            if self.path not in ("/delete", "/delete-all", "/delete-old"):
                return self.respond(404, "Not found", "text/plain; charset=utf-8")
            if self.headers.get("Origin") not in (None, f"http://127.0.0.1:{port}"):
                return self.respond(403, "Forbidden", "text/plain; charset=utf-8")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    return self.respond(400, "Bad request", "text/plain; charset=utf-8")
                data = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
                if data.get("csrf") != [token]:
                    return self.respond(403, "Forbidden", "text/plain; charset=utf-8")
                employee = str(json.loads(Path(report_path).read_text(encoding="utf-8"))["employee_id"])
                if self.path == "/delete":
                    day = data.get("date", [""])[0]
                    kind = data.get("kind", [""])[0]
                    if len(day) != 10 or kind not in ("attendance", "departure"):
                        return self.respond(400, "Bad request", "text/plain; charset=utf-8")
                    notes.delete(employee, day, kind)
                elif self.path == "/delete-all":
                    notes.delete_all(employee)
                else:
                    notes.delete_older_than(days=7)
            except (ValueError, OSError, KeyError):
                return self.respond(400, "Bad request", "text/plain; charset=utf-8")
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Review dashboard: http://127.0.0.1:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="local/missing_punch_report.json")
    parser.add_argument("--notes", default="local/missing_punch_notes.json")
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    serve(args.report, args.notes, args.port)
