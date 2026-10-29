#pragma once
// Shared helper for the new HTTPS station port. Never runs on HTTP port 80.
#include <Arduino.h>
static const char M9_LOGIN[] PROGMEM = R"M9LOGIN(<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0c1725"><title>دخول ZK Clock</title>
<style>body{background:#0c1725;color:white;font:17px system-ui;margin:10vh auto;padding:20px;max-width:440px}
main{background:#17283c;border:1px solid #2d455c;padding:24px;border-radius:17px}
h1{font-size:24px}label{display:block;margin:18px 0 4px}
input,button{font:inherit;padding:13px;width:100%;border-radius:9px}
input{background:#101b2c;border:1px solid #405972;color:#fff}
button{border:0;background:#2376cf;color:white;margin-top:22px}
small{color:#b4c7dc}#msg{color:#ffd28e}</style></head>
<body><main><small>HTTPS • ZK Clock</small><h1>تسجيل الدخول</h1>
<p>ادخل بيانات الحساب مرة واحدة. الجلسة تتجدد تلقائياً مع كل استخدام.</p>
<form id="login"><label for="user">المستخدم</label>
<input id="user" value="operator" autocomplete="username" maxlength="24" required>
<label for="pass">كلمة المرور</label>
<input id="pass" type="password" autocomplete="current-password" required>
<button>دخول</button></form><p id="msg"></p>
</main><script>
document.getElementById('login').onsubmit=async e=>{
 e.preventDefault();
 const body=new URLSearchParams({user:document.getElementById('user').value,
   password:document.getElementById('pass').value});
 try{
  const r=await fetch('/auth/login',{method:'POST',cache:'no-store',
  headers:{'Content-Type':'application/x-www-form-urlencoded'},
  body,credentials:'same-origin'});
  const j=await r.json();
  if(!r.ok||!j.ok)throw Error(j.error||'فشل الدخول');
  location.replace('/');
 }catch(e){document.getElementById('msg').textContent=e.message;}
};
</script></body></html>)M9LOGIN";
