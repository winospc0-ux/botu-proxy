// ===== Google Apps Script Proxy =====
// النشر: Deploy > New deployment > Web app
// تنفيذ كـ: Me, الوصول: Anyone
// حط الرابط في YT_WORKER

function doGet(e) {
  var target = e.parameter.url;
  if (!target) return ContentService.createTextOutput("?url=");
  
  try {
    var resp = UrlFetchApp.fetch(target, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
      },
      muteHttpExceptions: true,
      followRedirects: true,
    });
    
    var output = ContentService.createTextOutput(resp.getContentText());
    return output;
  } catch (e) {
    return ContentService.createTextOutput("GApps error: " + e.toString());
  }
}
