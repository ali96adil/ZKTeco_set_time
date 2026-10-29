#pragma once
// Password hash and rotating-on-login, revocable persistent browser sessions.
// An authenticated HTTPS hit renews a 1-year Secure cookie; active use
// therefore keeps the phone paired indefinitely (until logout/revoke).
#include <Arduino.h>
#include <Preferences.h>
#include <esp_system.h>
#include <mbedtls/sha256.h>
#include <cstring>
#include <cctype>

class ZkSessions {
  static constexpr unsigned kSlots = 4;
  static constexpr unsigned kRounds = 12000;
  String user_ = "operator";
  String salt_;
  String verifier_;
  String tokenHashes_[kSlots];
  uint8_t loginFailures_ = 0;
  uint32_t blockedUntil_ = 0;

  static String hex(const uint8_t *raw, size_t n) {
    static const char alphabet[] = "0123456789abcdef";
    String out;
    out.reserve(n*2);
    for (size_t i=0;i<n;++i) {
      out += alphabet[raw[i]>>4];
      out += alphabet[raw[i]&15];
    }
    return out;
  }
  static bool secureEq(const String& a,const String& b) {
    if (a.length()!=b.length()) return false;
    unsigned char difference=0;
    for (unsigned i=0;i<a.length();++i)difference |= a[i]^b[i];
    return difference==0;
  }
  static String randomHex(size_t bytes) {
    uint8_t tmp[32]={};
    if (bytes>sizeof(tmp)) bytes=sizeof(tmp);
    esp_fill_random(tmp,bytes);
    return hex(tmp,bytes);
  }
  static String hash(const String& text) {
    uint8_t digest[32];
    mbedtls_sha256_ret((const unsigned char*)text.c_str(),text.length(),digest,0);
    return hex(digest,32);
  }
  static String passwordDigest(const String& salt,const String& pass) {
    // Salted slow hash; do not persist or log the plaintext password.
    String current=hash(salt+":"+pass);
    for(unsigned i=0;i<kRounds;++i) {
      current=hash(current+salt);
      if((i&127)==0) delay(0); // yield to ESP32 watchdog during slow hashing
    }
    return current;
  }
  void load() {
    Preferences p;
    p.begin("zk-auth",true);
    user_=p.getString("user","operator");
    salt_=p.getString("salt","");
    verifier_=p.getString("hash","");
    for(unsigned i=0;i<kSlots;++i) {
      String key="s"+String(i);
      tokenHashes_[i]=p.getString(key.c_str(),"");
    }
    p.end();
  }
public:
  void begin(){load();}
  bool initialized() const {return salt_.length()>=32 && verifier_.length()==64;}
  String user() const {return user_;}
  bool configure(const String& newUser,const String& pass) {
    if (newUser.length()<3 || newUser.length()>24 ||
        pass.length()<12 || pass.length()>96) return false;
    for (unsigned i=0;i<newUser.length();++i)
      if (!isalnum((unsigned char)newUser[i]) && newUser[i]!='_' && newUser[i]!='-')
        return false;
    const String salt=randomHex(16);
    const String digest=passwordDigest(salt,pass);
    Preferences p;
    if(!p.begin("zk-auth",false))return false;
    bool ok=true;
    ok &= p.putString("user",newUser)>0;
    ok &= p.putString("salt",salt)>0;
    ok &= p.putString("hash",digest)>0;
    for(unsigned i=0;i<kSlots;++i) {
      String key="s"+String(i);
      p.remove(key.c_str());
    }
    p.end();
    if(ok){load();loginFailures_=0;blockedUntil_=0;}
    return ok;
  }
  String login(const String& user,const String& password) {
    if (!initialized()) return "";
    if (blockedUntil_ && (int32_t)(millis()-blockedUntil_)<0) return "";
    const String calc=passwordDigest(salt_,password);
    if(!secureEq(user,user_) || !secureEq(calc,verifier_)) {
      if(++loginFailures_>=5) {
        blockedUntil_=millis()+60000;
        loginFailures_=0;
      }
      return "";
    }
    loginFailures_=0;blockedUntil_=0;
    const String bearer=randomHex(32);
    const String tokenHash=hash(bearer);
    // Each successful login rotates the oldest slot, keeping <=4 phones.
    Preferences p;
    if(!p.begin("zk-auth",false))return "";
    for(int i=kSlots-1;i>0;--i) {
      String to="s"+String(i);
      p.putString(to.c_str(),tokenHashes_[i-1]);
    }
    p.putString("s0",tokenHash);
    p.end();
    load();
    return bearer;
  }
  static String parseCookie(const String& all) {
    int at=0;
    while(at<(int)all.length()) {
      int end=all.indexOf(';',at);if(end<0)end=all.length();
      String entry=all.substring(at,end);entry.trim();
      if(entry.startsWith("__Host-zkclock=")) {
        const String token=entry.substring(15);
        return token.length()==64 ? token : "";
      }
      at=end+1;
    }
    return "";
  }
  bool allowedCookie(const String& cookieHeader) const {
    const String token=parseCookie(cookieHeader);
    if (token.length()!=64) return false;
    const String candidate=hash(token);
    bool valid=false;
    for(unsigned i=0;i<kSlots;++i)
      valid |= tokenHashes_[i].length()==64 && secureEq(candidate,tokenHashes_[i]);
    return valid;
  }
  bool revokeAll() {
    Preferences p;
    if(!p.begin("zk-auth",false))return false;
    for(unsigned i=0;i<kSlots;++i) {
      String key="s"+String(i);p.remove(key.c_str());
    }
    p.end();load();
    return true;
  }
  static String issueCookie(const String& token) {
    // Refreshed with every authenticated response. Inactivity beyond one
    // browser year may require logging in again. Never HTTP or JavaScript.
    return "__Host-zkclock="+token+
      "; Path=/; Max-Age=31536000; Secure; HttpOnly; SameSite=Strict";
  }
  static const char* expireCookie() {
    return "__Host-zkclock=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Strict";
  }
};
